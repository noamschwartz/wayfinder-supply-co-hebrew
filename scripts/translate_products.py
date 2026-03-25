#!/usr/bin/env python3
"""Translate products.json to Hebrew with ₪ prices and °C temps."""
import json
import re
import math

# === MAPPINGS ===

CATEGORY_MAP = {
    "Camping": "קמפינג",
    "Hiking": "טיולים",
    "Climbing": "טיפוס",
    "Water Sports": "ספורט מים",
    "Winter Sports": "ספורט חורף",
    "Accessories": "אביזרים",
    "Apparel": "ביגוד",
    "Cycling": "אופניים",
    "Fishing": "דיג",
    "Tropical & Safari": "טרופי וספארי",
}

SUBCATEGORY_MAP = {
    "Tents - 3 Season": "אוהלים - 3 עונות",
    "Tents - 4 Season": "אוהלים - 4 עונות",
    "Sleeping Bags - Cold Weather": "שקי שינה - מזג אוויר קר",
    "Sleeping Bags - Warm Weather": "שקי שינה - מזג אוויר חם",
    "Sleeping Pads": "מזרוני שינה",
    "Camp Kitchen": "מטבח שטח",
    "Camp Furniture": "ריהוט שטח",
    "Backpacking Packs": "תיקי גב לטרקים",
    "Day Packs": "תיקי יום",
    "Hiking Boots": "נעלי הליכה",
    "Trail Running Shoes": "נעלי ריצת שטח",
    "Trekking Poles": "מקלות הליכה",
    "Hydration": "שתייה ומים",
    "Navigation": "ניווט",
    "Lighting & Power": "תאורה וחשמל",
    "First Aid & Safety": "עזרה ראשונה ובטיחות",
    "Multi-Tools & Knives": "כלים רב-שימושיים וסכינים",
    "Bags & Storage": "תיקים ואחסון",
    "Travel Accessories": "אביזרי טיול",
    "Ropes": "חבלים",
    "Harnesses": "רתמות",
    "Helmets": "קסדות",
    "Climbing Shoes": "נעלי טיפוס",
    "Protection & Hardware": "ציוד הגנה וחומרה",
    "Ice & Snow Gear": "ציוד קרח ושלג",
    "Avalanche Safety": "בטיחות מפולות",
    "Kayaks": "קיאקים",
    "Canoes": "קנואים",
    "Stand-Up Paddleboards": "סאפ - גלשני חתירה",
    "Paddles": "משוטים",
    "Life Vests & PFDs": "אפודות הצלה",
    "Wetsuits": "חליפות גלישה",
    "Dry Bags": "תיקים יבשים",
    "Snorkel & Dive Gear": "ציוד שנורקל וצלילה",
    "Skis - Downhill": "מגלשי סקי",
    "Skis - Cross Country": "סקי קרוס קאנטרי",
    "Snowboards": "סנובורד",
    "Snowshoes": "נעלי שלג",
    "Ski Boots": "מגפי סקי",
    "Goggles & Eyewear": "משקפי מגן ושמש",
    "Insulated Jackets": "מעילים מבודדים",
    "Softshell Jackets": "מעילי סופטשל",
    "Rain Gear": "ציוד גשם",
    "Base Layers": "שכבת בסיס",
    "Mid Layers": "שכבת ביניים",
    "Gloves": "כפפות",
    "Gaiters": "גייטרים",
    "Hiking Pants": "מכנסי טיול",
    "Shorts": "מכנסיים קצרים",
    "Mountain Bikes": "אופני הרים",
    "Bike Accessories": "אביזרי אופניים",
    "Bike Helmets": "קסדות אופניים",
    "Cycling Apparel": "ביגוד רכיבה",
    "Rods & Reels": "חכות וסלילים",
    "Tackle & Accessories": "ציוד דיג ואביזרים",
    "Waders": "מגפי דיג",
    "Ice Fishing Gear": "ציוד דיג בקרח",
    "Safari Essentials": "ציוד ספארי",
    "Sun Protection": "הגנה מהשמש",
    "Insect Protection": "הגנה מחרקים",
    "Cooling Gear": "ציוד קירור",
}

TAG_MAP = {
    "expedition": "משלחת",
    "family": "משפחתי",
    "professional": "מקצועי",
    "budget": "חסכוני",
    "ultralight": "אולטרלייט",
    "sustainable": "ירוק",
}

# USD to NIS conversion rate
USD_TO_NIS = 3.6

def convert_price(usd_price):
    """Convert USD to NIS and round nicely."""
    nis = usd_price * USD_TO_NIS
    if nis < 100:
        return round(nis / 5) * 5  # Round to nearest 5
    elif nis < 1000:
        return round(nis / 10) * 10  # Round to nearest 10
    else:
        return round(nis / 50) * 50  # Round to nearest 50


# === TITLE TRANSLATION ===
# Pattern: Keep brand name, translate the product type/descriptor

# Map common English product words to Hebrew
TITLE_WORD_MAP = {
    "Tent": "אוהל",
    "Sleeping Bag": "שק שינה",
    "Backpack": "תיק גב",
    "Pack": "תיק",
    "Stove": "כיריים",
    "Pad": "מזרון",
    "Mat": "מזרון",
    "Jacket": "מעיל",
    "Boot": "מגף",
    "Boots": "מגפיים",
    "Shoe": "נעל",
    "Shoes": "נעליים",
    "Gloves": "כפפות",
    "Poles": "מקלות",
    "Headlamp": "פנס ראש",
    "Helmet": "קסדה",
    "Harness": "רתמה",
    "Rope": "חבל",
    "Kayak": "קיאק",
    "Canoe": "קנואה",
    "Paddleboard": "גלשן חתירה",
    "Paddle": "משוט",
    "Wetsuit": "חליפת גלישה",
    "Ski": "מגלש סקי",
    "Skis": "מגלשי סקי",
    "Snowboard": "סנובורד",
    "Snowshoes": "נעלי שלג",
    "Bike": "אופניים",
    "Rod": "חכה",
    "Reel": "סליל",
}


def strip_type_suffix(model_part, subcategory):
    """Remove English type words from the model name, keeping just the model/series name."""
    # Words to strip from the end of model names (product type descriptors)
    type_words = [
        "3-Season Tent", "4-Season Tent", "Tent", "UL Tent",
        "Sleeping Bag", "Sleeping Pad", "Pad",
        "Backpack", "Pack", "Day Pack",
        "Stove", "Cookset", "Kitchen Set",
        "Chair", "Table", "Cot",
        "Hiking Boots", "Boots", "Trail Runners", "Trail Running Shoes", "Shoes",
        "Trekking Poles", "Poles",
        "Headlamp", "Lantern", "Power Bank",
        "First Aid Kit", "Kit",
        "Multi-Tool", "Knife",
        "Duffel", "Stuff Sack",
        "Rope", "Harness", "Helmet", "Carabiner",
        "Climbing Shoes",
        "Ice Axe", "Crampons",
        "Beacon", "Probe", "Shovel",
        "Kayak", "Canoe", "Paddleboard", "SUP",
        "Paddle", "PFD", "Life Vest",
        "Wetsuit", "Dry Bag",
        "Mask", "Snorkel Set", "Fins",
        "Skis", "Ski", "Snowboard", "Snowshoes", "Ski Boots",
        "Goggles", "Sunglasses",
        "Jacket", "Parka", "Puffer",
        "Softshell", "Rain Jacket", "Rain Pants", "Poncho",
        "Base Layer", "Top", "Bottom", "Leggings",
        "Fleece", "Midlayer",
        "Gloves", "Mittens",
        "Gaiters",
        "Pants", "Shorts",
        "Mountain Bike", "Bike",
        "Bike Light", "Bike Lock", "Bike Pump",
        "Bike Helmet",
        "Jersey", "Bib Shorts",
        "Rod", "Reel", "Combo",
        "Tackle Box", "Net",
        "Waders",
        "Ice Auger", "Ice Rod",
        "Safari Hat", "Binoculars",
        "Sun Shirt", "Sun Hat", "Sunscreen",
        "Bug Net", "Bug Spray",
        "Cooling Towel", "Cooling Vest",
    ]
    result = model_part
    for tw in sorted(type_words, key=len, reverse=True):  # longest first
        if result.lower().endswith(tw.lower()):
            result = result[:len(result) - len(tw)].strip().rstrip("-").strip()
            break
    return result if result else model_part


# Hebrew type names for titles (cleaner than full subcategory)
TITLE_TYPE_MAP = {
    "Tents - 3 Season": "אוהל 3 עונות",
    "Tents - 4 Season": "אוהל 4 עונות",
    "Sleeping Bags - Cold Weather": "שק שינה לקור",
    "Sleeping Bags - Warm Weather": "שק שינה קל",
    "Sleeping Pads": "מזרון שינה",
    "Camp Kitchen": "מטבח שטח",
    "Camp Furniture": "ריהוט שטח",
    "Backpacking Packs": "תיק גב",
    "Day Packs": "תיק יום",
    "Hiking Boots": "נעלי הליכה",
    "Trail Running Shoes": "נעלי ריצת שטח",
    "Trekking Poles": "מקלות הליכה",
    "Hydration": "מערכת שתייה",
    "Navigation": "ציוד ניווט",
    "Lighting & Power": "תאורה",
    "First Aid & Safety": "ערכת עזרה ראשונה",
    "Multi-Tools & Knives": "כלי רב-שימושי",
    "Bags & Storage": "תיק אחסון",
    "Travel Accessories": "אביזר טיול",
    "Ropes": "חבל טיפוס",
    "Harnesses": "רתמה",
    "Helmets": "קסדה",
    "Climbing Shoes": "נעלי טיפוס",
    "Protection & Hardware": "ציוד הגנה",
    "Ice & Snow Gear": "ציוד קרח ושלג",
    "Avalanche Safety": "ציוד בטיחות מפולות",
    "Kayaks": "קיאק",
    "Canoes": "קנואה",
    "Stand-Up Paddleboards": "גלשן חתירה",
    "Paddles": "משוט",
    "Life Vests & PFDs": "אפודת הצלה",
    "Wetsuits": "חליפת גלישה",
    "Dry Bags": "תיק יבש",
    "Snorkel & Dive Gear": "ציוד צלילה",
    "Skis - Downhill": "מגלשי סקי",
    "Skis - Cross Country": "סקי קרוס קאנטרי",
    "Snowboards": "סנובורד",
    "Snowshoes": "נעלי שלג",
    "Ski Boots": "מגפי סקי",
    "Goggles & Eyewear": "משקפי מגן",
    "Insulated Jackets": "מעיל מבודד",
    "Softshell Jackets": "מעיל סופטשל",
    "Rain Gear": "ציוד גשם",
    "Base Layers": "שכבת בסיס",
    "Mid Layers": "שכבת ביניים",
    "Gloves": "כפפות",
    "Gaiters": "גייטרים",
    "Hiking Pants": "מכנסי טיול",
    "Shorts": "מכנסיים קצרים",
    "Mountain Bikes": "אופני הרים",
    "Bike Accessories": "אביזרי אופניים",
    "Bike Helmets": "קסדת אופניים",
    "Cycling Apparel": "ביגוד רכיבה",
    "Rods & Reels": "חכה וסליל",
    "Tackle & Accessories": "ציוד דיג",
    "Waders": "מגפי דיג",
    "Ice Fishing Gear": "ציוד דיג בקרח",
    "Safari Essentials": "ציוד ספארי",
    "Sun Protection": "הגנה מהשמש",
    "Insect Protection": "הגנה מחרקים",
    "Cooling Gear": "ציוד קירור",
}


def translate_title(title, brand, subcategory):
    """Translate product title: keep brand + model name, add Hebrew type.

    Example: 'Wayfinder Supply Summit Seeker 3-Season Tent'
    → 'Wayfinder Supply Summit Seeker - אוהל 3 עונות'
    """
    # Remove brand from title to get model + type
    model_part = title.replace(brand, "").strip()

    # Strip the English type suffix to get just the model name
    model_name = strip_type_suffix(model_part, subcategory)

    # Get Hebrew type name
    he_type = TITLE_TYPE_MAP.get(subcategory, SUBCATEGORY_MAP.get(subcategory, subcategory))

    if model_name:
        return f"{brand} {model_name} - {he_type}"
    else:
        return f"{brand} - {he_type}"


# === DESCRIPTION TEMPLATES ===
# Generate natural Hebrew descriptions based on subcategory and tags

def generate_hebrew_description(product):
    """Generate a natural Hebrew product description."""
    brand = product["brand"]
    title = product["title"]
    subcat = product["subcategory"]
    cat = product["category"]
    tags = product.get("tags", [])
    price_nis = convert_price(product["price"])

    tag_descriptors = []
    if "ultralight" in tags:
        tag_descriptors.append("קל משקל במיוחד")
    if "expedition" in tags:
        tag_descriptors.append("מיועד למשלחות ולטיולים ארוכים")
    if "family" in tags:
        tag_descriptors.append("מתאים לכל המשפחה")
    if "budget" in tags:
        tag_descriptors.append("במחיר נגיש")
    if "professional" in tags:
        tag_descriptors.append("ברמה מקצועית")
    if "sustainable" in tags:
        tag_descriptors.append("מיוצר מחומרים ידידותיים לסביבה")

    tag_str = ", ".join(tag_descriptors) if tag_descriptors else ""

    # Category-specific templates
    templates = {
        "Tents - 3 Season": f"אוהל 3 עונות של {brand}, מושלם לקמפינג באביב, קיץ וסתיו. עמיד בפני רוח וגשם קל, עם מרחב פנימי נוח ואוורור מעולה. {tag_str}. קל להקמה ונוח לנשיאה בטיולים.",
        "Tents - 4 Season": f"אוהל 4 עונות של {brand}, בנוי להתמודד עם תנאי מזג אוויר קיצוניים כולל שלג כבד ורוחות חזקות. מבנה חזק ובידוד מעולה לטיולי חורף ומשלחות הרים. {tag_str}.",
        "Sleeping Bags - Cold Weather": f"שק שינה לקור של {brand}, מבודד ומחמם גם בטמפרטורות מתחת לאפס. מילוי איכותי, רוכסן דו-כיווני וכיסוי לראש. {tag_str}.",
        "Sleeping Bags - Warm Weather": f"שק שינה קל של {brand}, מושלם ללילות קיץ חמים. אוורור מצוין, קל משקל ונוח לאריזה. {tag_str}.",
        "Sleeping Pads": f"מזרון שינה של {brand}, מספק בידוד מהקרקע ונוחות מירבית. קל לניפוח ולאחסון, מתאים לכל סוגי הטיולים. {tag_str}.",
        "Camp Kitchen": f"ציוד מטבח שטח של {brand}. קומפקטי, עמיד ויעיל – מושלם להכנת ארוחות בשטח. {tag_str}.",
        "Camp Furniture": f"ריהוט שטח של {brand}, נוח וקל לנשיאה. מתקפל בקלות ועמיד בתנאי שטח. {tag_str}.",
        "Backpacking Packs": f"תיק גב לטרקים של {brand}, עם מערכת נשיאה ארגונומית ונוחה. תאים מרובים, גישה קלה לציוד ורצועות מתכווננות. {tag_str}.",
        "Day Packs": f"תיק יום של {brand}, קל ונוח לטיולי יום. תאים מאורגנים, מערכת שתייה ורצועות נוחות. {tag_str}.",
        "Hiking Boots": f"נעלי הליכה של {brand}, עם סוליה אוחזת ותמיכה מעולה לקרסול. עמידות במים ונוחות לטיולים ארוכים. {tag_str}.",
        "Trail Running Shoes": f"נעלי ריצת שטח של {brand}, קלות ומהירות עם אחיזה מצוינת. מתאימות לשבילים טכניים ומשטחים מגוונים. {tag_str}.",
        "Trekking Poles": f"מקלות הליכה של {brand}, קלים וחזקים עם נעילה מהירה. מפחיתים עומס על הברכיים ומשפרים יציבות בשטח. {tag_str}.",
        "Hydration": f"מערכת שתייה של {brand}, נוחה לשימוש תוך כדי תנועה. עמידה, קלה לניקוי ומתאימה לכל תיק. {tag_str}.",
        "Navigation": f"ציוד ניווט של {brand}, אמין ומדויק. מושלם לטיולים בשטח פתוח ובתנאי שטח מאתגרים. {tag_str}.",
        "Lighting & Power": f"ציוד תאורה וחשמל של {brand}, עוצמתי וחסכוני באנרגיה. מושלם לקמפינג ולטיולי לילה. {tag_str}.",
        "First Aid & Safety": f"ערכת עזרה ראשונה של {brand}, מקיפה וקומפקטית. כוללת את כל הנדרש למצבי חירום בשטח. {tag_str}.",
        "Multi-Tools & Knives": f"כלי רב-שימושי של {brand}, חזק ורב-תכליתי. מושלם לכל מטלה בשטח. {tag_str}.",
        "Bags & Storage": f"תיק אחסון של {brand}, עמיד ומאורגן. שומר על הציוד מסודר ומוגן. {tag_str}.",
        "Travel Accessories": f"אביזר טיול של {brand}, שימושי ונוח. מוסיף נוחות וארגון לכל מסע. {tag_str}.",
        "Ropes": f"חבל טיפוס של {brand}, חזק ואמין. מיוצר מחומרים באיכות הגבוהה ביותר לבטיחות מירבית. {tag_str}.",
        "Harnesses": f"רתמת טיפוס של {brand}, נוחה ובטוחה. מתאימה למגוון פעילויות גובה עם מערכת אבזמים מהירה. {tag_str}.",
        "Helmets": f"קסדת טיפוס של {brand}, קלה וחזקה. הגנה מירבית עם אוורור מעולה. {tag_str}.",
        "Climbing Shoes": f"נעלי טיפוס של {brand}, עם אחיזה מעולה ורגישות גבוהה. מתאימות לטיפוס בסלע ובקיר. {tag_str}.",
        "Protection & Hardware": f"ציוד הגנה וחומרה לטיפוס של {brand}. עמיד, אמין ומאושר לפי תקנים בינלאומיים. {tag_str}.",
        "Ice & Snow Gear": f"ציוד קרח ושלג של {brand}, מיועד לתנאים קיצוניים. חזק, אמין ומתאים למשלחות חורף. {tag_str}.",
        "Avalanche Safety": f"ציוד בטיחות מפולות של {brand}. חיוני לכל פעילות חורפית בהרים – מסייע באיתור ובחילוץ. {tag_str}.",
        "Kayaks": f"קיאק של {brand}, יציב ומהיר במים. מתאים למתחילים ולמנוסים כאחד. {tag_str}.",
        "Canoes": f"קנואה של {brand}, יציבה ומרווחת. מושלמת לטיולי מים ולשיט מנוחה. {tag_str}.",
        "Stand-Up Paddleboards": f"גלשן חתירה (SUP) של {brand}, יציב וקל לשימוש. מתאים לים, לאגם ולנהר. {tag_str}.",
        "Paddles": f"משוט של {brand}, קל וחזק. עיצוב ארגונומי לחתירה יעילה. {tag_str}.",
        "Life Vests & PFDs": f"אפודת הצלה של {brand}, נוחה ובטוחה. מאושרת לפי תקנים בינלאומיים עם התאמה מושלמת. {tag_str}.",
        "Wetsuits": f"חליפת גלישה של {brand}, גמישה ומבודדת. שומרת על חום הגוף במים קרים. {tag_str}.",
        "Dry Bags": f"תיק יבש של {brand}, אטום למים לחלוטין. שומר על הציוד יבש בכל תנאי. {tag_str}.",
        "Snorkel & Dive Gear": f"ציוד שנורקל וצלילה של {brand}, איכותי ונוח. מתאים לחקירת עולם הים. {tag_str}.",
        "Skis - Downhill": f"מגלשי סקי של {brand}, עם ביצועים מעולים במדרונות. מתאימים למגוון תנאי שלג ורמות מיומנות. {tag_str}.",
        "Skis - Cross Country": f"מגלשי סקי קרוס קאנטרי של {brand}, קלים ומהירים. מושלמים לסקי שטח ולאימוני סיבולת. {tag_str}.",
        "Snowboards": f"סנובורד של {brand}, עם שליטה מעולה וגמישות. מתאים לפארק, לפיסט ולשטח. {tag_str}.",
        "Snowshoes": f"נעלי שלג של {brand}, קלות ויציבות. מאפשרות הליכה נוחה בשלג עמוק. {tag_str}.",
        "Ski Boots": f"מגפי סקי של {brand}, נוחים ומדויקים. מספקים תמיכה ושליטה מעולה. {tag_str}.",
        "Goggles & Eyewear": f"משקפי מגן של {brand}, עם הגנת UV מלאה וראות מצוינת. מתאימים לסקי, לטיולים ולפעילות חוצות. {tag_str}.",
        "Insulated Jackets": f"מעיל מבודד של {brand}, מחמם וקל. מילוי איכותי ששומר על חום הגוף גם בקור קיצוני. {tag_str}.",
        "Softshell Jackets": f"מעיל סופטשל של {brand}, גמיש ועמיד ברוח. מושלם לפעילות אינטנסיבית בתנאי מזג אוויר משתנים. {tag_str}.",
        "Rain Gear": f"ציוד גשם של {brand}, אטום למים ונושם. שומר עליכם יבשים בכל תנאי מזג אוויר. {tag_str}.",
        "Base Layers": f"שכבת בסיס של {brand}, נושמת ומנדפת זיעה. שומרת על טמפרטורת גוף אופטימלית. {tag_str}.",
        "Mid Layers": f"שכבת ביניים של {brand}, מחממת ונושמת. מושלמת כשכבה נוספת מתחת למעיל. {tag_str}.",
        "Gloves": f"כפפות של {brand}, מחממות ונוחות. אחיזה מעולה גם בתנאים רטובים. {tag_str}.",
        "Gaiters": f"גייטרים של {brand}, מגנים על הרגליים מפני אבנים, בוץ ושלג. קלים ועמידים. {tag_str}.",
        "Hiking Pants": f"מכנסי טיול של {brand}, נוחים ועמידים. גמישות מרבית עם הגנה מפני שריטות ומזג אוויר. {tag_str}.",
        "Shorts": f"מכנסיים קצרים של {brand}, קלים ונוחים. מושלמים לפעילות חוצות בימים חמים. {tag_str}.",
        "Mountain Bikes": f"אופני הרים של {brand}, עם מתלים ובולמים איכותיים. מתאימים לשטח טכני ולשבילים מאתגרים. {tag_str}.",
        "Bike Accessories": f"אביזרי אופניים של {brand}, משפרים את חוויית הרכיבה. עמידים ופרקטיים. {tag_str}.",
        "Bike Helmets": f"קסדת אופניים של {brand}, קלה ובטוחה. אוורור מעולה והגנה מירבית. {tag_str}.",
        "Cycling Apparel": f"ביגוד רכיבה של {brand}, נושם ואירודינמי. נוחות מרבית בכל מרחק. {tag_str}.",
        "Rods & Reels": f"חכה וסליל של {brand}, רגישים וחזקים. מתאימים לדיג במים מתוקים ובים. {tag_str}.",
        "Tackle & Accessories": f"ציוד דיג ואביזרים של {brand}. כל מה שצריך ליום דיג מוצלח. {tag_str}.",
        "Waders": f"מגפי דיג של {brand}, אטומים למים ונוחים. מאפשרים דיג בתוך המים בנוחות. {tag_str}.",
        "Ice Fishing Gear": f"ציוד דיג בקרח של {brand}, עמיד בקור קיצוני. מיועד לדייגים מנוסים. {tag_str}.",
        "Safari Essentials": f"ציוד ספארי של {brand}, מותאם לתנאים טרופיים. קל, נושם ועמיד. {tag_str}.",
        "Sun Protection": f"ציוד הגנה מהשמש של {brand}. מגן מפני קרני UV עם נוחות מרבית. {tag_str}.",
        "Insect Protection": f"ציוד הגנה מחרקים של {brand}. יעיל ובטוח לשימוש בטבע. {tag_str}.",
        "Cooling Gear": f"ציוד קירור של {brand}, שומר על קרירות בתנאי חום קיצוניים. {tag_str}.",
    }

    desc = templates.get(subcat, f"ציוד {SUBCATEGORY_MAP.get(subcat, subcat)} של {brand}. איכותי, עמיד ומתאים לפעילות חוצות. {tag_str}.")

    # Clean up double spaces and trailing dots
    desc = re.sub(r'\s+', ' ', desc).strip()
    desc = re.sub(r'\.\s*\.', '.', desc)
    desc = re.sub(r',\s*\.', '.', desc)

    return desc


def translate_product(product):
    """Translate a single product to Hebrew."""
    translated = product.copy()

    # Translate category
    translated["category"] = CATEGORY_MAP.get(product["category"], product["category"])

    # Translate subcategory
    translated["subcategory"] = SUBCATEGORY_MAP.get(product["subcategory"], product["subcategory"])

    # Translate tags
    translated["tags"] = [TAG_MAP.get(t, t) for t in product.get("tags", [])]

    # Convert price
    translated["price"] = convert_price(product["price"])

    # Translate title
    translated["title"] = translate_title(product["title"], product["brand"], product["subcategory"])

    # Generate Hebrew description
    translated["description"] = generate_hebrew_description(product)

    return translated


def main():
    input_path = "generated_products/products.json"
    output_path = "generated_products/products.json"

    with open(input_path, "r", encoding="utf-8") as f:
        products = json.load(f)

    translated = [translate_product(p) for p in products]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(translated, f, ensure_ascii=False, indent=2)

    print(f"Translated {len(translated)} products")
    print(f"Output: {output_path}")

    # Print sample
    sample = translated[0]
    print(f"\nSample:")
    print(f"  Title: {sample['title']}")
    print(f"  Category: {sample['category']}")
    print(f"  Subcategory: {sample['subcategory']}")
    print(f"  Price: ₪{sample['price']}")
    print(f"  Tags: {sample['tags']}")
    print(f"  Description: {sample['description'][:100]}...")


if __name__ == "__main__":
    main()
