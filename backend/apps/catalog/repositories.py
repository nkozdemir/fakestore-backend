from apps.common.repository import GenericRepository
from .models import Category, Product, Rating


class CategoryRepository(GenericRepository[Category]):
    def __init__(self):
        super().__init__(Category)

    def detach_from_products(self, category: Category):
        """
        Remove relationships between the category and any products before deletion.
        """
        category.products.clear()


class ProductRepository(GenericRepository[Product]):
    def __init__(self):
        super().__init__(Product)

    def list(self, **filters):  # type: ignore[override]
        """Return products with categories prefetched to avoid N+1 during DTO mapping."""
        return self.model.objects.filter(**filters).prefetch_related("categories")

    def list_by_category(self, category_name: str):
        return self.model.objects.filter(
            categories__name=category_name
        ).prefetch_related("categories")

    def list_by_category_ids(self, category_ids):
        return (
            self.model.objects.filter(categories__id__in=category_ids)
            .distinct()
            .prefetch_related("categories")
        )

    # --- Helper methods for service orchestration ---
    def set_categories(self, product: Product, category_ids):
        from .models import Category  # local import to avoid circulars in migrations

        qs = Category.objects.filter(id__in=category_ids) if category_ids else []
        product.categories.set(qs)

    def update_scalar(self, product: Product, **fields):
        dirty = False
        for k, v in fields.items():
            if v is not None:
                setattr(product, k, v)
                dirty = True
        if dirty:
            product.save()
        return product

    def recalculate_rating(self, product: Product):
        from django.db.models import Avg, Count

        agg = product.ratings.aggregate(avg=Avg("value"), count=Count("id"))
        count = agg["count"] or 0
        if not count:
            product.rate = 0
            product.count = 0
        else:
            product.rate = round(float(agg["avg"]) + 1e-8, 1)
            product.count = count
        product.save(update_fields=["rate", "count"])
        return product


class RatingRepository(GenericRepository[Rating]):
    def __init__(self):
        super().__init__(Rating)

    def for_product_user(self, product_id: int, user_id: int):
        return self.model.objects.filter(product_id=product_id, user_id=user_id).first()

    def list_for_product(self, product_id: int):
        return (
            self.model.objects.filter(product_id=product_id)
            .select_related("user")
            .order_by("-updated_at")
        )
