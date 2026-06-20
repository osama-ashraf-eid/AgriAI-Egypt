import re

GOVERNORATES = [
    "القاهرة", "الجيزة", "الإسكندرية", "الفيوم", "المنيا",
    "أسيوط", "سوهاج", "قنا", "الأقصر", "أسوان", "البحيرة",
    "الدقهلية", "الغربية", "المنوفية", "القليوبية", "الشرقية",
    "كفر الشيخ", "دمياط", "بورسعيد", "الإسماعيلية", "السويس",
    "شمال سيناء", "جنوب سيناء", "الوادي الجديد", "مطروح",
    "البحر الأحمر", "بني سويف",
]

GOV_ALIASES = {
    "فيوم":     "الفيوم",
    "اسكندرية": "الإسكندرية",
    "اسكندريه": "الإسكندرية",
    "قاهرة":    "القاهرة",
    "جيزه":     "الجيزة",
    "بحيره":    "البحيرة",
    "منيا":     "المنيا",
    "منيه":     "المنيا",
    "اسيوط":    "أسيوط",
    "بورسعيد":  "بورسعيد",
}

def normalize_arabic(text: str) -> str:
    if not text:
        return ""
    # إزالة التشكيل والتنوين والعلّامات
    text = re.sub(r'[\u0617-\u061A\u064B-\u065F]', '', text)
    # توحيد الألفات والهمزات
    text = re.sub(r'[\u0622\u0623\u0625\u0671]', '\u0627', text)
    # توحيد التاء المربوطة والهاء
    text = re.sub(r'\u0629', '\u0647', text)
    text = re.sub(r'\u0624', '\u0648', text)
    # توحيد الياء المقصورة والياء العادية
    text = re.sub(r'[\u0626\u0649]', '\u064A', text)
    # إزالة الكشيدة (التطويل)
    text = re.sub(r'\u0640', '', text)
    # تنظيف المسافات البيضاء المتعددة
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_governorate(text: str) -> str:
    normalized = normalize_arabic(text)
    for alias, standard in GOV_ALIASES.items():
        if alias in normalized:
            return standard
    for gov in GOVERNORATES:
        if normalize_arabic(gov) in normalized:
            return gov
    return ""

def extract_price_range(price: float) -> str:
    if price <= 15:
        return "low"
    elif price <= 40:
        return "medium"
    else:
        return "high"