from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def ensure_single_cart(apps, schema_editor):
    Cart = apps.get_model("carts", "Cart")
    CartProduct = apps.get_model("carts", "CartProduct")
    User = apps.get_model("users", "User")

    for user in User.objects.all():
        carts = list(Cart.objects.filter(user_id=user.id).order_by("id"))
        if user.is_staff or user.is_superuser:
            for extra in carts:
                CartProduct.objects.filter(cart_id=extra.id).delete()
                extra.delete()
            continue
        if carts:
            keeper = carts[0]
            # Drop any additional carts and their products
            for extra in carts[1:]:
                CartProduct.objects.filter(cart_id=extra.id).delete()
                extra.delete()
        else:
            Cart.objects.create(user_id=user.id, date=timezone.now().date())


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
        ("carts", "0003_alter_cart_id"),
    ]

    atomic = False

    operations = [
        migrations.RunPython(ensure_single_cart, migrations.RunPython.noop),
        migrations.RunSQL("SET CONSTRAINTS ALL IMMEDIATE", reverse_sql=migrations.RunSQL.noop),
        migrations.AlterField(
            model_name="cart",
            name="user",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="cart",
                to="users.user",
            ),
        ),
    ]
