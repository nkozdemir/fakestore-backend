from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0003_auto_product_autofield"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["title"], name="product_title_idx"),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["rate"], name="product_rate_idx"),
        ),
        migrations.AddIndex(
            model_name="rating",
            index=models.Index(fields=["product"], name="rating_product_idx"),
        ),
        migrations.AddIndex(
            model_name="productcategory",
            index=models.Index(
                fields=["product", "category"], name="prod_cat_combo_idx"
            ),
        ),
    ]
