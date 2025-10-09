import types
import unittest
from apps.catalog.services import ProductService, CategoryService


class FakeCache:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, timeout=None):
        self.store[key] = value


class StubCategory:
    def __init__(self, category_id: int, name: str):
        self.id = category_id
        self.name = name


class StubCategoryManager:
    def __init__(self, categories=None):
        self._categories = list(categories or [])

    def all(self):
        return list(self._categories)

    def set(self, categories):
        self._categories = list(categories)


class StubProduct:
    def __init__(self, product_id: int, title: str, price: str, description: str = '', image: str = ''):
        self.id = product_id
        self.title = title
        self.price = price
        self.description = description
        self.image = image
        self.rate = 0.0
        self.count = 0
        self.categories = StubCategoryManager()
        self._ratings = {}


class FakeCategoryRepository:
    def __init__(self):
        self._categories = {}
        self._pk = 1

    def create(self, **data):
        category = StubCategory(self._pk, data['name'])
        self._categories[self._pk] = category
        self._pk += 1
        return category

    def list(self, **filters):
        return list(self._categories.values())

    def get(self, **filters):
        category_id = filters.get('id')
        return self._categories.get(category_id)

    def delete(self, category: StubCategory):
        self._categories.pop(category.id, None)


class FakeProductRepository:
    def __init__(self, category_repo: FakeCategoryRepository):
        self.category_repo = category_repo
        self._products = {}
        self._pk = 1

    def create(self, **data):
        product = StubProduct(self._pk, data['title'], str(data['price']), data.get('description', ''), data.get('image', ''))
        self._products[self._pk] = product
        self._pk += 1
        return product

    def get(self, **filters):
        product_id = filters.get('id')
        return self._products.get(product_id)

    def list(self, **filters):
        return list(self._products.values())

    def list_by_category(self, category_name: str):
        return [p for p in self._products.values() if any(c.name == category_name for c in p.categories.all())]

    def list_by_category_ids(self, category_ids):
        return [p for p in self._products.values() if any(c.id in category_ids for c in p.categories.all())]

    def set_categories(self, product: StubProduct, category_ids):
        categories = [self.category_repo.get(id=cid) for cid in category_ids if self.category_repo.get(id=cid)]
        product.categories.set(categories)

    def update_scalar(self, product: StubProduct, **fields):
        for key, value in fields.items():
            if value is not None:
                setattr(product, key, value)
        return product

    def delete(self, product: StubProduct):
        self._products.pop(product.id, None)

    def recalculate_rating(self, product: StubProduct):
        values = list(product._ratings.values())
        if not values:
            product.rate = 0.0
            product.count = 0
        else:
            product.count = len(values)
            product.rate = round(sum(values) / product.count, 1)
        return product


class StubRating:
    def __init__(self, repo, product_id: int, user_id: int, value: int):
        self._repo = repo
        self.product_id = product_id
        self.user_id = user_id
        self.value = value

    def save(self):
        self._repo._set_rating(self.product_id, self.user_id, self.value)

    def delete(self):
        self._repo._delete_rating(self.product_id, self.user_id)


class FakeRatingRepository:
    def __init__(self, product_repo: FakeProductRepository):
        self.product_repo = product_repo
        self._ratings = {}

    def for_product_user(self, product_id: int, user_id: int):
        key = (product_id, user_id)
        value = self._ratings.get(key)
        if value is None:
            return None
        return StubRating(self, product_id, user_id, value)

    def create(self, **data):
        product_id = data['product_id']
        user_id = data['user_id']
        value = data['value']
        self._ratings[(product_id, user_id)] = value
        product = self.product_repo.get(id=product_id)
        product._ratings[user_id] = value
        self.product_repo.recalculate_rating(product)
        return StubRating(self, product_id, user_id, value)

    def _set_rating(self, product_id: int, user_id: int, value: int):
        self._ratings[(product_id, user_id)] = value
        product = self.product_repo.get(id=product_id)
        product._ratings[user_id] = value
        self.product_repo.recalculate_rating(product)

    def _delete_rating(self, product_id: int, user_id: int):
        self._ratings.pop((product_id, user_id), None)
        product = self.product_repo.get(id=product_id)
        if product and user_id in product._ratings:
            product._ratings.pop(user_id)
            self.product_repo.recalculate_rating(product)


class ProductServiceUnitTests(unittest.TestCase):
    def setUp(self):
        self.category_repo = FakeCategoryRepository()
        self.product_repo = FakeProductRepository(self.category_repo)
        self.rating_repo = FakeRatingRepository(self.product_repo)
        self.cache = FakeCache()
        self.service = ProductService(
            products=self.product_repo,
            ratings=self.rating_repo,
            cache_backend=self.cache,
            disable_cache=True,
        )

    def test_create_and_get_product(self):
        cat = self.category_repo.create(name="Books")
        dto = self.service.create_product({
            'title': 'Novel',
            'price': '12.50',
            'description': 'A book',
            'image': 'img',
            'categories': [cat.id]
        })
        fetched = self.service.get_product(dto.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.title, 'Novel')
        self.assertEqual(len(fetched.categories), 1)

    def test_update_product(self):
        product = self.product_repo.create(title='Item', price='1.00', description='d', image='i')
        updated = self.service.update_product(product.id, {
            'title': 'Item2',
            'price': '2.00',
            'description': 'd2',
            'image': 'i2'
        }, partial=False)
        self.assertEqual(updated.title, 'Item2')
        self.assertEqual(updated.price, '2.00')

    def test_rating_cycle(self):
        product = self.product_repo.create(title='Rated', price='5.00', description='d', image='i')
        summary = self.service.set_user_rating(product.id, user_id=10, value=4)
        self.assertEqual(summary['rating']['count'], 1)
        self.assertEqual(summary['rating']['rate'], 4.0)
        summary = self.service.set_user_rating(product.id, user_id=10, value=5)
        self.assertEqual(summary['rating']['rate'], 5.0)
        summary = self.service.delete_user_rating(product.id, user_id=10)
        self.assertEqual(summary['rating']['count'], 0)

    def test_list_products_cache_hit(self):
        service_cache = ProductService(
            products=self.product_repo,
            ratings=self.rating_repo,
            cache_backend=self.cache,
            disable_cache=False,
        )
        self.product_repo.create(title='Cached', price='9.99', description='d', image='i')
        original_list = self.product_repo.list
        call_counter = {'count': 0}

        def tracked_list(self, **filters):
            call_counter['count'] += 1
            return original_list(**filters)

        self.product_repo.list = types.MethodType(tracked_list, self.product_repo)
        first = service_cache.list_products()
        second = service_cache.list_products()
        self.assertEqual(call_counter['count'], 1)
        self.assertEqual(first, second)
        self.product_repo.list = original_list

    def test_cache_version_bumped_on_mutations(self):
        service_cache = ProductService(
            products=self.product_repo,
            ratings=self.rating_repo,
            cache_backend=self.cache,
            disable_cache=False,
        )
        dto = service_cache.create_product({'title': 'New', 'price': '1.00', 'description': '', 'image': ''})
        version_after_create = self.cache.get(service_cache._cache_version_key)
        self.assertEqual(version_after_create, service_cache._default_version + 1)
        service_cache.update_product(dto.id, {'title': 'Updated'}, partial=True)
        version_after_update = self.cache.get(service_cache._cache_version_key)
        self.assertEqual(version_after_update, service_cache._default_version + 2)
        service_cache.delete_product(dto.id)
        version_after_delete = self.cache.get(service_cache._cache_version_key)
        self.assertEqual(version_after_delete, service_cache._default_version + 3)

    def test_rating_validation_and_missing_product(self):
        error = self.service.set_user_rating(999, user_id=1, value=4)
        self.assertEqual(error[0], 'NOT_FOUND')
        error = self.service.set_user_rating(self.product_repo._pk, user_id=1, value=10)
        self.assertEqual(error[0], 'VALIDATION_ERROR')
        summary = self.service.get_rating_summary(999)
        self.assertIsNone(summary)


class CategoryServiceUnitTests(unittest.TestCase):
    def setUp(self):
        self.category_repo = FakeCategoryRepository()
        self.service = CategoryService(categories=self.category_repo)

    def test_create_list_delete_category(self):
        dto = self.service.create_category({'name': 'Toys'})
        self.assertEqual(dto.name, 'Toys')
        categories = self.service.list_categories()
        self.assertTrue(any(c.name == 'Toys' for c in categories))
        deleted = self.service.delete_category(dto.id)
        self.assertTrue(deleted)
