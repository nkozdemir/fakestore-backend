from django.core.management.base import BaseCommand
from django.db import transaction, connection
from django.core.management.color import no_style
from django.utils import timezone
from apps.catalog.models import Category, Product, ProductCategory
from apps.users.models import User, Address
from apps.carts.models import Cart, CartProduct

CATEGORIES = [
    "men's clothing",
    "jewelery",
    "electronics",
    "women's clothing",
]

PRODUCTS = [
    (
        1,
        "Fjallraven - Foldsack No. 1 Backpack, Fits 15 Laptops",
        109.95,
        "Your perfect pack for everyday use and walks in the forest. Stash your laptop (up to 15 inches) in the padded sleeve, your everyday",
        "https://fakestoreapi.com/img/81fPKd-2AYL._AC_SL1500_t.png",
        0,
        0,
        ["men's clothing"],
    ),
    (
        2,
        "Mens Casual Premium Slim Fit T-Shirts ",
        22.30,
        "Slim-fitting style, contrast raglan long sleeve, three-button henley placket, light weight & soft fabric for breathable and comfortable wearing. And Solid stitched shirts with round neck made for durability and a great fit for casual fashion wear and diehard baseball fans. The Henley style round neckline includes a three-button placket.",
        "https://fakestoreapi.com/img/71-3HjGNDUL._AC_SY879._SX._UX._SY._UY_t.png",
        0,
        0,
        ["men's clothing"],
    ),
    (
        3,
        "Mens Cotton Jacket",
        55.99,
        "great outerwear jackets for Spring/Autumn/Winter, suitable for many occasions, such as working, hiking, camping, mountain/rock climbing, cycling, traveling or other outdoors. Good gift choice for you or your family member. A warm hearted love to Father, husband or son in this thanksgiving or Christmas Day.",
        "https://fakestoreapi.com/img/71li-ujtlUL._AC_UX679_t.png",
        0,
        0,
        ["men's clothing"],
    ),
    (
        4,
        "Mens Casual Slim Fit",
        15.99,
        "The color could be slightly different between on the screen and in practice. / Please note that body builds vary by person, therefore, detailed size information should be reviewed below on the product description.",
        "https://fakestoreapi.com/img/71YXzeOuslL._AC_UY879_t.png",
        0,
        0,
        ["men's clothing"],
    ),
    (
        5,
        "John Hardy Women's Legends Naga Gold & Silver Dragon Station Chain Bracelet",
        695.00,
        "From our Legends Collection, the Naga was inspired by the mythical water dragon that protects the ocean's pearl. Wear facing inward to be bestowed with love and abundance, or outward for protection.",
        "https://fakestoreapi.com/img/71pWzhdJNwL._AC_UL640_QL65_ML3_t.png",
        0,
        0,
        ["jewelery"],
    ),
    (
        6,
        "Solid Gold Petite Micropave ",
        168.00,
        "Satisfaction Guaranteed. Return or exchange any order within 30 days.Designed and sold by Hafeez Center in the United States. Satisfaction Guaranteed. Return or exchange any order within 30 days.",
        "https://fakestoreapi.com/img/61sbMiUnoGL._AC_UL640_QL65_ML3_t.png",
        0,
        0,
        ["jewelery"],
    ),
    (
        7,
        "White Gold Plated Princess",
        9.99,
        "Classic Created Wedding Engagement Solitaire Diamond Promise Ring for Her. Gifts to spoil your love more for Engagement, Wedding, Anniversary, Valentine's Day...",
        "https://fakestoreapi.com/img/71YAIFU48IL._AC_UL640_QL65_ML3_t.png",
        0,
        0,
        ["jewelery"],
    ),
    (
        8,
        "Pierced Owl Rose Gold Plated Stainless Steel Double",
        10.99,
        "Rose Gold Plated Double Flared Tunnel Plug Earrings. Made of 316L Stainless Steel",
        "https://fakestoreapi.com/img/51UDEzMJVpL._AC_UL640_QL65_ML3_t.png",
        0,
        0,
        ["jewelery"],
    ),
    (
        9,
        "WD 2TB Elements Portable External Hard Drive - USB 3.0 ",
        64.00,
        "USB 3.0 and USB 2.0 Compatibility Fast data transfers Improve PC Performance High Capacity; Compatibility Formatted NTFS for Windows 10, Windows 8.1, Windows 7; Reformatting may be required for other operating systems; Compatibility may vary depending on user’s hardware configuration and operating system",
        "https://fakestoreapi.com/img/61IBBVJvSDL._AC_SY879_t.png",
        0,
        0,
        ["electronics"],
    ),
    (
        10,
        "SanDisk SSD PLUS 1TB Internal SSD - SATA III 6 Gb/s",
        109.00,
        "Easy upgrade for faster boot up, shutdown, application load and response (As compared to 5400 RPM SATA 2.5” hard drive; Based on published specifications and internal benchmarking tests using PCMark vantage scores) Boosts burst write performance, making it ideal for typical PC workloads The perfect balance of performance and reliability Read/write speeds of up to 535MB/s/450MB/s (Based on internal testing; Performance may vary depending upon drive capacity, host device, OS and application.)",
        "https://fakestoreapi.com/img/61U7T1koQqL._AC_SX679_t.png",
        0,
        0,
        ["electronics"],
    ),
    (
        11,
        "Silicon Power 256GB SSD 3D NAND A55 SLC Cache Performance Boost SATA III 2.5",
        109.00,
        "3D NAND flash are applied to deliver high transfer speeds Remarkable transfer speeds that enable faster bootup and improved overall system performance. The advanced SLC Cache Technology allows performance boost and longer lifespan 7mm slim design suitable for Ultrabooks and Ultra-slim notebooks. Supports TRIM command, Garbage Collection technology, RAID, and ECC (Error Checking & Correction) to provide the optimized performance and enhanced reliability.",
        "https://fakestoreapi.com/img/71kWymZ+c+L._AC_SX679_t.png",
        0,
        0,
        ["electronics"],
    ),
    (
        12,
        "WD 4TB Gaming Drive Works with Playstation 4 Portable External Hard Drive",
        114.00,
        "Expand your PS4 gaming experience, Play anywhere Fast and easy, setup Sleek design with high capacity, 3-year manufacturer's limited warranty",
        "https://fakestoreapi.com/img/61mtL65D4cL._AC_SX679_t.png",
        0,
        0,
        ["electronics"],
    ),
    (
        13,
        "Acer SB220Q bi 21.5 inches Full HD (1920 x 1080) IPS Ultra-Thin",
        599.00,
        "21. 5 inches Full HD (1920 x 1080) widescreen IPS display And Radeon free Sync technology. No compatibility for VESA Mount Refresh Rate: 75Hz - Using HDMI port Zero-frame design | ultra-thin | 4ms response time | IPS panel Aspect ratio - 16: 9. Color Supported - 16. 7 million colors. Brightness - 250 nit Tilt angle -5 degree to 15 degree. Horizontal viewing angle-178 degree. Vertical viewing angle-178 degree 75 hertz",
        "https://fakestoreapi.com/img/81QpkIctqPL._AC_SX679_t.png",
        0,
        0,
        ["electronics"],
    ),
    (
        14,
        "Samsung 49-Inch CHG90 144Hz Curved Gaming Monitor (LC49HG90DMNXZA) – Super Ultrawide Screen QLED ",
        999.99,
        "49 INCH SUPER ULTRAWIDE 32:9 CURVED GAMING MONITOR with dual 27 inch screen side by side QUANTUM DOT (QLED) TECHNOLOGY, HDR support and factory calibration provides stunningly realistic and accurate color and contrast 144HZ HIGH REFRESH RATE and 1ms ultra fast response time work to eliminate motion blur, ghosting, and reduce input lag",
        "https://fakestoreapi.com/img/81Zt42ioCgL._AC_SX679_t.png",
        0,
        0,
        ["electronics"],
    ),
    (
        15,
        "BIYLACLESEN Women's 3-in-1 Snowboard Jacket Winter Coats",
        56.99,
        "Note:The Jackets is US standard size, Please choose size as your usual wear Material: 100% Polyester; Detachable Liner Fabric: Warm Fleece. Detachable Functional Liner: Skin Friendly, Lightweigt and Warm.Stand Collar Liner jacket, keep you warm in cold weather. Zippered Pockets: 2 Zippered Hand Pockets, 2 Zippered Pockets on Chest (enough to keep cards or keys)and 1 Hidden Pocket Inside.Zippered Hand Pockets and Hidden Pocket keep your things secure. Humanized Design: Adjustable and Detachable Hood and Adjustable cuff to prevent the wind and water,for a comfortable fit. 3 in 1 Detachable Design provide more convenience, you can separate the coat and inner as needed, or wear it together. It is suitable for different season and help you adapt to different climates",
        "https://fakestoreapi.com/img/51Y5NI-I5jL._AC_UX679_t.png",
        0,
        0,
        ["women's clothing"],
    ),
    (
        16,
        "Lock and Love Women's Removable Hooded Faux Leather Moto Biker Jacket",
        29.95,
        "100% POLYURETHANE(shell) 100% POLYESTER(lining) 75% POLYESTER 25% COTTON (SWEATER), Faux leather material for style and comfort / 2 pockets of front, 2-For-One Hooded denim style faux leather jacket, Button detail on waist / Detail stitching at sides, HAND WASH ONLY / DO NOT BLEACH / LINE DRY / DO NOT IRON",
        "https://fakestoreapi.com/img/81XH0e8fefL._AC_UY879_t.png",
        0,
        0,
        ["women's clothing"],
    ),
    (
        17,
        "Rain Jacket Women Windbreaker Striped Climbing Raincoats",
        39.99,
        "Lightweight perfet for trip or casual wear---Long sleeve with hooded, adjustable drawstring waist design. Button and zipper front closure raincoat, fully stripes Lined and The Raincoat has 2 side pockets are a good size to hold all kinds of things, it covers the hips, and the hood is generous but doesn't overdo it.Attached Cotton Lined Hood with Adjustable Drawstrings give it a real styled look.",
        "https://fakestoreapi.com/img/71HblAHs5xL._AC_UY879_-2t.png",
        0,
        0,
        ["women's clothing"],
    ),
    (
        18,
        "MBJ Women's Solid Short Sleeve Boat Neck V ",
        9.85,
        "95% RAYON 5% SPANDEX, Made in USA or Imported, Do Not Bleach, Lightweight fabric with great stretch for comfort, Ribbed on sleeves and neckline / Double stitching on bottom hem",
        "https://fakestoreapi.com/img/71z3kpMAYsL._AC_UY879_t.png",
        0,
        0,
        ["women's clothing"],
    ),
    (
        19,
        "Opna Women's Short Sleeve Moisture",
        7.95,
        "100% Polyester, Machine wash, 100% cationic polyester interlock, Machine Wash & Pre Shrunk for a Great Fit, Lightweight, roomy and highly breathable with moisture wicking fabric which helps to keep moisture away, Soft Lightweight Fabric with comfortable V-neck collar and a slimmer fit, delivers a sleek, more feminine silhouette and Added Comfort",
        "https://fakestoreapi.com/img/51eg55uWmdL._AC_UX679_t.png",
        0,
        0,
        ["women's clothing"],
    ),
    (
        20,
        "DANVOUY Womens T Shirt Casual Cotton Short",
        12.99,
        "95%Cotton,5%Spandex, Features: Casual, Short Sleeve, Letter Print,V-Neck,Fashion Tees, The fabric is soft and has some stretch., Occasion: Casual/Office/Beach/School/Home/Street. Season: Spring,Summer,Autumn,Winter.",
        "https://fakestoreapi.com/img/61pHAEJ4NML._AC_UX679_t.png",
        0,
        0,
        ["women's clothing"],
    ),
]

USERS = [
    {
        "id": 1,
        "first_name": "john",
        "last_name": "doe",
        "email": "john@gmail.com",
        "username": "johnd",
        "password": "m38rmF$",
        "phone": "1-570-236-7033",
    },
    {
        "id": 2,
        "first_name": "david",
        "last_name": "morrison",
        "email": "morrison@gmail.com",
        "username": "mor_2314",
        "password": "83r5^_",
        "phone": "1-570-236-7033",
    },
    {
        "id": 3,
        "first_name": "kevin",
        "last_name": "ryan",
        "email": "kevin@gmail.com",
        "username": "kevinryan",
        "password": "kev02937@",
        "phone": "1-567-094-1345",
    },
    {
        "id": 4,
        "first_name": "don",
        "last_name": "romer",
        "email": "don@gmail.com",
        "username": "donero",
        "password": "ewedon",
        "phone": "1-765-789-6734",
    },
    {
        "id": 5,
        "first_name": "derek",
        "last_name": "powell",
        "email": "derek@gmail.com",
        "username": "derek",
        "password": "jklg*_56",
        "phone": "1-956-001-1945",
    },
    {
        "id": 6,
        "first_name": "david",
        "last_name": "russell",
        "email": "david_r@gmail.com",
        "username": "david_r",
        "password": "3478*#54",
        "phone": "1-678-345-9856",
    },
    {
        "id": 7,
        "first_name": "miriam",
        "last_name": "snyder",
        "email": "miriam@gmail.com",
        "username": "snyder",
        "password": "f238&@*$",
        "phone": "1-123-943-0563",
    },
    {
        "id": 8,
        "first_name": "william",
        "last_name": "hopkins",
        "email": "william@gmail.com",
        "username": "hopkins",
        "password": "William56$hj",
        "phone": "1-478-001-0890",
    },
    {
        "id": 9,
        "first_name": "kate",
        "last_name": "hale",
        "email": "kate@gmail.com",
        "username": "kate_h",
        "password": "kfejk@*_",
        "phone": "1-678-456-1934",
    },
    {
        "id": 10,
        "first_name": "jimmie",
        "last_name": "klein",
        "email": "jimmie@gmail.com",
        "username": "jimmie_k",
        "password": "klein*#%*",
        "phone": "1-104-001-4567",
    },
    {
        "id": 11,
        "first_name": "admin",
        "last_name": "user",
        "email": "admin@fakestore.com",
        "username": "admin",
        "password": "AdminPass123!",
        "is_superuser": True
    },
    {
        "id": 12,
        "first_name": "staff",
        "last_name": "user",
        "email": "staff@fakestore.com",
        "username": "staff",
        "password": "StaffPass123!",
        "is_staff": True
    }
]

ADDRESSES = [
    (1, "new road", 7682, "kilcoole", "12926-3874", -37.3159, 81.1496),
    (2, "Lovers Ln", 7267, "kilcoole", "12926-3874", -37.3159, 81.1496),
    (3, "Frances Ct", 86, "Cullman", "29567-1452", 40.3467, -30.1310),
    (4, "Hunters Creek Dr", 6454, "San Antonio", "98234-1734", 50.3467, -20.1310),
    (5, "adams St", 245, "san Antonio", "80796-1234", 40.3467, -40.1310),
    (6, "prospect st", 124, "el paso", "12346-0456", 20.1677, -10.6789),
    (7, "saddle st", 1342, "fresno", "96378-0245", 10.3456, 20.6419),
    (8, "vally view ln", 1342, "mesa", "96378-0245", 50.3456, 10.6419),
    (9, "avondale ave", 345, "miami", "96378-0245", 40.12456, 20.5419),
    (10, "oak lawn ave", 526, "fort wayne", "10256-4532", 30.24788, -20.545419),
]


class Command(BaseCommand):
    help = "Seed the entire fakestore dataset in one operation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush", action="store_true", help="Delete existing data before seeding"
        )

    @transaction.atomic
    def handle(self, *args, **options):
        def reset_sequences(models):
            """Reset database sequences for given models (PostgreSQL, etc.)."""
            sql_list = connection.ops.sequence_reset_sql(no_style(), models)
            if not sql_list:
                return
            with connection.cursor() as cursor:
                for sql in sql_list:
                    cursor.execute(sql)

        if options["flush"]:
            self.stdout.write("Flushing existing data...")
            CartProduct.objects.all().delete()
            Cart.objects.all().delete()
            Address.objects.all().delete()
            User.objects.all().delete()
            ProductCategory.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()

        self.stdout.write("Seeding categories...")
        name_to_cat = {}
        for name in CATEGORIES:
            cat, _ = Category.objects.get_or_create(name=name)
            name_to_cat[name] = cat

        self.stdout.write("Seeding products...")
        for pid, title, price, desc, image, rate, count, cat_names in PRODUCTS:
            product, _ = Product.objects.get_or_create(
                id=pid,
                defaults=dict(
                    title=title,
                    price=price,
                    description=desc,
                    image=image,
                    rate=rate,
                    count=count,
                ),
            )
            for cname in cat_names:
                ProductCategory.objects.get_or_create(
                    product=product, category=name_to_cat[cname]
                )

        self.stdout.write("Seeding users...")
        for payload in USERS:
            attrs = dict(payload)
            user_id = attrs.pop("id")
            raw_password = attrs.pop("password")
            is_superuser = attrs.get("is_superuser", False)
            # Superusers must also be staff
            is_staff = attrs.get("is_staff", False) or is_superuser
            defaults = {
                "first_name": attrs["first_name"],
                "last_name": attrs["last_name"],
                "email": attrs["email"],
                "username": attrs["username"],
                "phone": attrs.get("phone"),
                "is_staff": is_staff,
                "is_superuser": is_superuser,
            }
            user, created = User.objects.get_or_create(id=user_id, defaults=defaults)
            if not created:
                for field, value in defaults.items():
                    setattr(user, field, value)
            user.set_password(raw_password)
            user.save()

        # Important: After inserting explicit IDs, reset the user ID sequence so
        # future inserts (e.g., via the API) don't try to reuse an existing PK.
        # We'll reset sequences for models that may rely on DB sequences
        # after we've finished inserting all explicit IDs.

        self.stdout.write("Seeding addresses...")
        for user_id, street, number, city, zipcode, lat, lon in ADDRESSES:
            user = User.objects.get(id=user_id)
            Address.objects.get_or_create(
                user=user,
                street=street,
                number=number,
                city=city,
                zipcode=zipcode,
                latitude=lat,
                longitude=lon,
            )

        self.stdout.write("Ensuring empty carts for all users...")
        CartProduct.objects.all().delete()
        today = timezone.now().date()
        for user in User.objects.all():
            Cart.objects.update_or_create(
                user=user,
                defaults={"date": today},
            )

        # After inserting explicit IDs, reset sequences for these models so future
        # inserts use the next available ID (prevents duplicate key IntegrityError).
        reset_sequences([User, Product, Cart])

        self.stdout.write(self.style.SUCCESS("FakeStore seed completed."))
