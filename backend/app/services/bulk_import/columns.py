from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnSpec:
    key: str            # canonical field name on Product
    title: str          # Persian header shown in template
    required: bool
    example: str
    description: str
    aliases: tuple[str, ...] = ()  # likely user header variants


# Single source of truth for the bulk-import schema.
# `title` matches the header row in the generated xlsx template.
# `aliases` are used by the column-mapping auto-detector to suggest a mapping
# when a user uploads a file with their own header names.
COLUMNS: tuple[ColumnSpec, ...] = (
    ColumnSpec(
        key="name",
        title="نام محصول",
        required=True,
        example="عسل طبیعی کوهی ۵۰۰ گرمی",
        description="نام کامل محصول طبق قواعد SEO باسلام (با نام دسته شروع کن).",
        aliases=("نام", "title", "product_name", "name"),
    ),
    ColumnSpec(
        key="category_title",
        title="دسته‌بندی",
        required=True,
        example="عسل",
        description="عنوان فارسی دسته‌بندی باسلام. سرور بر اساس عنوان match می‌کند.",
        aliases=("دسته", "گروه", "category", "category_name", "type"),
    ),
    ColumnSpec(
        key="primary_price",
        title="قیمت (تومان)",
        required=True,
        example="285000",
        description="قیمت فروش به تومان. فقط عدد (بدون کاما).",
        aliases=("قیمت", "قیمت فروش", "price", "primary_price", "sale_price"),
    ),
    ColumnSpec(
        key="stock",
        title="موجودی",
        required=True,
        example="12",
        description="تعداد موجود انبار. عدد صحیح غیرمنفی.",
        aliases=("تعداد", "موجودی انبار", "stock", "inventory", "qty", "quantity"),
    ),
    ColumnSpec(
        key="weight_g",
        title="وزن خالص (گرم)",
        required=False,
        example="500",
        description="وزن خالص محصول به گرم. اگر مایع است معادل گرم را وارد کن.",
        aliases=("وزن", "وزن خالص", "weight", "net_weight"),
    ),
    ColumnSpec(
        key="package_weight_g",
        title="وزن با بسته‌بندی (گرم)",
        required=True,
        example="560",
        description="وزن کل با بسته‌بندی، باید بزرگ‌تر از وزن خالص باشد.",
        aliases=(
            "وزن بسته‌بندی",
            "وزن کل",
            "package_weight",
            "packaged_weight",
            "gross_weight",
        ),
    ),
    ColumnSpec(
        key="preparation_days",
        title="روز آماده‌سازی",
        required=True,
        example="3",
        description="چند روز طول می‌کشد محصول آماده ارسال شود.",
        aliases=(
            "آماده سازی",
            "زمان آماده سازی",
            "preparation_days",
            "lead_time",
            "prep_days",
        ),
    ),
    ColumnSpec(
        key="brief",
        title="معرفی کوتاه",
        required=False,
        example="عسل خام و طبیعی از کوه‌های زاگرس",
        description="یک پاراگراف کوتاه برای معرفی محصول.",
        aliases=("خلاصه", "summary", "brief", "short_description"),
    ),
    ColumnSpec(
        key="description",
        title="توضیحات",
        required=False,
        example="توضیحات کامل محصول شامل ویژگی‌ها و نحوه مصرف...",
        description="متن کامل توضیحات. می‌تواند چندخطی باشد.",
        aliases=("توضیحات کامل", "description", "details", "long_description"),
    ),
    ColumnSpec(
        key="keywords",
        title="کلمات کلیدی",
        required=False,
        example="عسل، طبیعی، کوهی، ارگانیک",
        description="فهرست کلمات کلیدی برای جستجو، با کاما جدا کن.",
        aliases=("کلیدواژه", "تگ", "keywords", "tags"),
    ),
    ColumnSpec(
        key="sku",
        title="کد انبار (SKU)",
        required=False,
        example="HONEY-500-A1",
        description="کد داخلی محصول برای انبار. اختیاری.",
        aliases=("SKU", "کد محصول", "sku", "product_code"),
    ),
    ColumnSpec(
        key="barcode",
        title="بارکد",
        required=False,
        example="1234567890123",
        description="بارکد ۸ تا ۱۳ رقمی روی محصول. اختیاری.",
        aliases=("barcode", "ean", "upc"),
    ),
    ColumnSpec(
        key="unit_quantity",
        title="مقدار واحد فروش",
        required=False,
        example="500",
        description="مقدار هر واحد فروش (مثلاً ۵۰۰ برای ۵۰۰ گرم).",
        aliases=("مقدار", "unit_quantity", "sale_quantity"),
    ),
    ColumnSpec(
        key="unit_type_title",
        title="واحد فروش",
        required=False,
        example="گرم",
        description="نام فارسی واحد فروش: گرم، کیلوگرم، لیتر، عددی، بسته، …",
        aliases=("واحد", "unit", "unit_type"),
    ),
    ColumnSpec(
        key="is_wholesale",
        title="عمده‌فروشی",
        required=False,
        example="false",
        description="فروش عمده است؟ true یا false (پیش‌فرض false).",
        aliases=("عمده", "wholesale", "is_wholesale"),
    ),
    ColumnSpec(
        key="image_urls",
        title="لینک عکس‌ها",
        required=False,
        example="https://i.imgur.com/abc.jpg, https://i.imgur.com/def.jpg",
        description="یک یا چند URL عمومی عکس، با کاما جدا. سرور دانلود و آپلود می‌کند.",
        aliases=("عکس", "تصویر", "image", "image_url", "photo", "photos"),
    ),
    ColumnSpec(
        key="image_filenames",
        title="نام فایل عکس‌ها در ZIP",
        required=False,
        example="honey-1.jpg, honey-2.jpg",
        description=(
            "اگر فایل را به‌صورت ZIP فرستادی و عکس‌ها داخل پوشه images/ هستند، "
            "نام دقیق فایل‌های این محصول را با کاما جدا کن."
        ),
        aliases=("فایل عکس", "image_filenames", "image_files"),
    ),
)


def column_by_key(key: str) -> ColumnSpec | None:
    for col in COLUMNS:
        if col.key == key:
            return col
    return None


def required_keys() -> tuple[str, ...]:
    return tuple(c.key for c in COLUMNS if c.required)
