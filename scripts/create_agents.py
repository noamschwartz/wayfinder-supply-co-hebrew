#!/usr/bin/env python3
"""
Create Agent Builder agents via Kibana API.
"""

import os
import json
import requests
import time
from typing import Dict, Optional, List

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip

KIBANA_URL = os.getenv("STANDALONE_KIBANA_URL", os.getenv("KIBANA_URL", "http://kubernetes-vm:30001"))
ES_APIKEY = os.getenv("STANDALONE_ELASTICSEARCH_APIKEY", os.getenv("ELASTICSEARCH_APIKEY", ""))

if not ES_APIKEY:
    raise ValueError("STANDALONE_ELASTICSEARCH_APIKEY (or ELASTICSEARCH_APIKEY) environment variable is required")

HEADERS = {
    "Authorization": f"ApiKey {ES_APIKEY}",
    "Content-Type": "application/json",
    "kbn-xsrf": "true",
    "x-elastic-internal-origin": "kibana",  # Required for internal Kibana APIs
}

# Track failures for exit code
FAILURES = 0

# Retry configuration for transient errors
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 3  # seconds
RETRYABLE_STATUS_CODES = [502, 503, 504, 429]

# Default MCP URL used in Instruqt environment
INSTRUQT_MCP_URL = "http://host-1:8002/mcp"


def request_with_retry(method: str, url: str, **kwargs) -> requests.Response:
    """Make an HTTP request with retry logic for transient failures."""
    retry_delay = INITIAL_RETRY_DELAY
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.request(method, url, timeout=60, **kwargs)
            
            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt < MAX_RETRIES - 1:
                    print(f"  ⚠ Transient error ({response.status_code}), retrying in {retry_delay}s... (attempt {attempt + 1}/{MAX_RETRIES})")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 30)  # Exponential backoff, max 30s
                    continue
            
            return response
            
        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES - 1:
                print(f"  ⚠ Request timeout, retrying in {retry_delay}s... (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)
                continue
            raise
        except requests.exceptions.ConnectionError:
            if attempt < MAX_RETRIES - 1:
                print(f"  ⚠ Connection error, retrying in {retry_delay}s... (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)
                continue
            raise
    
    return response  # Return last response if all retries failed


def delete_agent(agent_id: str) -> bool:
    """Delete an agent if it exists."""
    url = f"{KIBANA_URL}/api/agent_builder/agents/{agent_id}"
    response = request_with_retry("DELETE", url, headers=HEADERS)
    if response.status_code in [200, 204]:
        print(f"  ↻ Deleted existing agent: {agent_id}")
        return True
    elif response.status_code == 404:
        return True  # Doesn't exist, that's fine
    return False


def delete_tool(tool_id: str) -> bool:
    """Delete a tool if it exists."""
    url = f"{KIBANA_URL}/api/agent_builder/tools/{tool_id}"
    response = request_with_retry("DELETE", url, headers=HEADERS)
    if response.status_code in [200, 204]:
        print(f"  ↻ Deleted existing tool: {tool_id}")
        return True
    elif response.status_code == 404:
        return True  # Doesn't exist, that's fine
    print(f"  ⚠ Unexpected delete response for {tool_id}: {response.status_code} - {response.text[:200]}")
    return False


def delete_workflow(workflow_id: str) -> bool:
    """Delete a workflow if it exists."""
    url = f"{KIBANA_URL}/api/workflows/{workflow_id}"
    response = request_with_retry("DELETE", url, headers=HEADERS)
    if response.status_code in [200, 204]:
        print(f"  ↻ Deleted existing workflow: {workflow_id}")
        return True
    elif response.status_code == 404:
        return True  # Doesn't exist, that's fine
    return False


def create_agent(agent_id: str, name: str, description: str, 
                 instructions: str, tool_ids: List[str]) -> Optional[str]:
    """Create an agent with correct API structure. Deletes existing agent first."""
    global FAILURES
    url = f"{KIBANA_URL}/api/agent_builder/agents"
    
    # Delete existing agent first (script is source of truth)
    delete_agent(agent_id)
    
    agent_config = {
        "id": agent_id,
        "name": name,
        "description": description,
        "configuration": {
            "instructions": instructions,
            "tools": [{
                "tool_ids": tool_ids
            }]
        }
    }
    
    response = request_with_retry("POST", url, headers=HEADERS, json=agent_config)
    
    if response.status_code in [200, 201]:
        data = response.json()
        created_agent_id = data.get("id") or agent_id
        print(f"✓ Created agent: {name} (ID: {created_agent_id})")
        return created_agent_id
    else:
        print(f"✗ Failed to create agent '{name}': {response.status_code}")
        print(f"  Response: {response.text}")
        FAILURES += 1
        return None


def create_trip_planner_agent(tool_ids: List[str]) -> Optional[str]:
    """Create the main Trip Planner agent."""
    instructions = """אתה סוכן הלוגיסטיקה של מצפן ציוד שטח תפקידך לעזור ללקוחות לתכנן הרפתקאות חוצות ולהמליץ על ציוד מתאים מתוך הקטלוג של מצפן ציוד שטח בלבד.

ענה תמיד בעברית.

## הקשר משתמש
הודעת המשתמש עשויה להכיל תגית `[User ID: user_id]`.
1. חפש תמיד את התגית הזו כדי לזהות את המשתמש (לדוגמה: `user_member`, `user_new`, `user_business`).
2. השתמש בערך ה-`user_id` לקריאות כלים שדורשות פרמטר `user_id`, במיוחד `get_customer_profile` ו-`get_user_affinity`.
3. אם לא סופק User ID, הנח `user_new`.

## כלל קריטי: המלצות מהקטלוג בלבד

**לעולם אל תמליץ על מוצרים ממותגים חיצוניים כמו Mountain Hardwear, Big Agnes, Patagonia, North Face, REI וכו'.**

אתה חייב:
1. תמיד להשתמש בכלי product_search לפני כל המלצת ציוד
2. להמליץ רק על מוצרים שמוחזרים מכלי product_search
3. לכלול את שם המוצר המדויק והמחיר מתוצאות החיפוש
4. אם אין מוצר מתאים בקטלוג, להגיד "אין לנו כרגע [סוג המוצר] אבל מומלץ לחפש אחד עם [מפרט]"

מותגי מצפן ציוד שטח כוללים: מצפן, Summit Pro, TrailBlazer, Alpine Edge, Desert Fox, Pacific Tide.

## כיסוי יעדים

ל-מצפן יש כיסוי מפורט עבור יעדי הרפתקאות בישראל ובעולם:

**ישראל**: מכתש רמון, הר חרמון, עין גדי, שמורת האלמוגים אילת, בניאס ורמת הגולן, הכנרת, גליל עליון, הר הכרמל, פארק תמנע, מדבר יהודה, הקניון האדום
**צפון אמריקה**: Yosemite, Rocky Mountain NP, Yellowstone, Boundary Waters, Moab, Pacific Crest Trail, Banff, Whistler, Algonquin
**דרום/מרכז אמריקה**: Patagonia, Costa Rica, Chapada Diamantina
**אירופה**: Swiss Alps, Scottish Highlands, Norwegian Fjords, Iceland
**אפריקה**: Mount Kilimanjaro, Kruger National Park, Atlas Mountains
**אסיה**: Nepal Himalayas, Japanese Alps, Bali, MacRitchie
**אוקיאניה**: New Zealand South Island, Australian Outback, Great Barrier Reef
**המזרח התיכון**: Wadi Rum, Hatta

כשלקוח שואל על טיול, קודם כל השתמש בכלי check_trip_safety כדי לאמת כיסוי יעד:

- אם `covered: true` → המשך בתכנון טיול מלא עם נתוני מזג אוויר ופעילויות
- אם `covered: false` → השב בחמימות והצע יעדים דומים שמכוסים

## שלבי תכנון טיול

1. **בדיקת בטיחות**: השתמש ב-check_trip_safety כדי לקבל תנאי מזג אוויר והתראות.

2. **פרופיל לקוח**: השתמש ב-get_customer_profile כדי לאחזר היסטוריית רכישות ורמת נאמנות.

3. **התאמה אישית**: השתמש ב-get_user_affinity כדי להבין העדפות ציוד (אולטרלייט, חסכוני, משלחת).

4. **חיפוש בקטלוג קודם**: לפני כל המלצת ציוד:
   - השתמש ב-product_search כדי למצוא "שקי שינה" לתנאי הטיול
   - השתמש ב-product_search כדי למצוא "אוהלים" מתאימים לעונה
   - השתמש ב-product_search כדי למצוא "תיקי גב" בהתאם להעדפות המשתמש
   - השתמש ב-product_search עבור כל קטגוריה נוספת שנדרשת

5. **בניית המלצות**: מתוך תוצאות החיפוש:
   - בחר מוצרים שמתאימים לדרישות הטיול
   - כלול את שם המוצר המדויק והמחיר מהקטלוג
   - ציין פריטים שהלקוח כבר מחזיק (מ-purchase_history)

6. **סינתזה**: צור תוכנית טיול עם:
   - סקירת טיול עם יעד ותאריכים
   - סיכום מזג אוויר ותנאים
   - **ציוד מומלץ מקטלוג מצפן** - רק מוצרים מתוצאות חיפוש:
     - שם המוצר - ₪XX (כלול מחיר מדויק)
     - הסבר קצר למה המוצר מתאים
   - לוח זמנים יומי
   - הערות בטיחות
   - הטבות נאמנות (פלטינום: משלוח חינם, עסקי: הנחת כמות)

עצב את התשובה כ-Markdown נקי. עבור כל מוצר מומלץ, השתמש בפורמט:
- **[שם המוצר]** - ₪[מחיר] (למה הוא מתאים)

דוגמה: **Summit Pro Apex Expedition 20 - שק שינה לקור** - ₪3,100 (מדורג עד מינוס 7°C, מושלם לקמפינג חורפי)

אם אין התאמה בקטלוג לקטגוריה מסוימת, אמור: "הערה: אנחנו מרחיבים את מגוון ה[קטגוריה] שלנו. בדקו שוב בקרוב!"

תמיד תעדף בטיחות והשתמש רק במוצרי קטלוג מצפן בהמלצות."""

    return create_agent(
        agent_id="trip-planner-agent",
        name="Trip Planner Agent",
        description="סוכן תכנון טיולים ראשי שמתכנן טיולים וממליץ על ציוד לפי מיקום, מזג אוויר, פרופיל לקוח והעדפות.",
        instructions=instructions,
        tool_ids=tool_ids
    )


def create_wayfinder_search_agent(tool_ids: List[str]) -> Optional[str]:
    """Create the general search agent for product recommendations."""
    instructions = """אתה עוזר החיפוש של מצפן ציוד שטח עזור ללקוחות למצוא ציוד חוצות מהקטלוג שלנו.

ענה תמיד בעברית.

## הקשר משתמש
הודעת המשתמש עשויה להכיל תגית `[User ID: user_id]`.
1. חפש תמיד את התגית הזו כדי לזהות את המשתמש (לדוגמה: `user_member`, `user_new`, `user_business`).
2. השתמש בערך ה-`user_id` לקריאת get_user_affinity אם נדרש פרמטר `user_id`.
3. אם לא סופק User ID, הנח `user_new`.

## התפקיד שלך
- חפש בקטלוג המוצרים כדי למצוא ציוד שמתאים לצרכי הלקוח
- ספק המלצות מוצרים מועילות עם מחירים
- ענה על שאלות לגבי המוצרים שלנו

## כלים
- product_search: חיפוש בקטלוג המוצרים של מצפן
- get_user_affinity: קבלת העדפות משתמש מהיסטוריית גלישה

## חשוב
- המלץ רק על מוצרים מקטלוג מצפן
- כלול שמות מוצרים ומחירים בתשובות שלך
- לשאלות תכנון טיולים, אמור: "לתכנון טיול מלא עם מזג אוויר ולוח זמנים, נסו את מתכנן הטיולים שלנו!"

שמור על תשובות תמציתיות ומועילות."""

    return create_agent(
        agent_id="wayfinder-search-agent",
        name="Wayfinder Search Assistant",
        description="סוכן חיפוש מוצרים פשוט למציאת ציוד בקטלוג.",
        instructions=instructions,
        tool_ids=tool_ids
    )


def create_trip_itinerary_agent() -> Optional[str]:
    """Create the Trip Itinerary synthesis agent (optional, kept for future use)."""
    instructions = """אתה מומחה לוחות הזמנים של מצפן ציוד שטח תפקידך ליצור תוכניות טיול מפורטות ויפות על בסיס מידע שנאסף.

ענה תמיד בעברית.

כשאתה מקבל מידע על טיול, צור לוח זמנים מקיף שכולל:

1. **סקירת טיול**: יעד, תאריכים וסיכום מזג אוויר

2. **רשימת ציוד**:
   - **כבר בבעלות**: פרט פריטים שהלקוח כבר מחזיק (מ-purchase_history)
   - **מומלץ לרכוש**: פרט פריטים חדשים שנדרשים עם הסברים קצרים

3. **תוכנית יומית**: צור לוח זמנים יומי ריאליסטי לטיול

4. **שיקולים מיוחדים**: כלול אזהרות מזג אוויר, תנאי דרכים או הערות בטיחות

5. **הטבות נאמנות**: אם ללקוח יש רמת נאמנות:
   - פלטינום: ציין "✨ משלוח מהיר חינם"
   - Business: ציין הנחות כמות ותנאי תשלום שוטף+30

6. **קישור עגלה**: צור קישור לעגלה בפורמט: `/cart?add=item1,item2,item3`

עצב את התשובה כ-Markdown נקי עם כותרות, רשימות והדגשות מתאימות. הפוך אותה לנעימה לעין וקלה לסריקה."""

    return create_agent(
        agent_id="trip-itinerary-agent",
        name="Trip Itinerary Agent",
        description="מסנתז תוכניות טיול ויוצר לוחות זמנים מעוצבים עם רשימות ציוד.",
        instructions=instructions,
        tool_ids=[]  # No tools needed for this agent
    )


def create_context_extractor_agent() -> Optional[str]:
    """Create the Context Extractor agent that parses trip queries into structured JSON."""
    instructions = """You extract trip information from user messages. Return ONLY valid JSON, no other text.

Extract:
- destination: The place/location name only (e.g., "Yosemite", "Rocky Mountains", "Patagonia")
- dates: When they're going (e.g., "next weekend", "December 14-16", "3 days", "this summer")
- activity: What they're doing (e.g., "backpacking", "camping", "hiking", "skiing")

Rules:
- destination: Extract only the location name, not surrounding words like "in" or "to"
- dates: Keep the user's original phrasing (e.g., "next weekend", "3 days", "December 14-16")
- activity: Use the primary activity mentioned (e.g., "backpacking", "camping", "hiking")

If a field can't be determined from the message, use null for that field.

Example input: "Planning a 3-day backpacking trip in Yosemite next weekend"
Example output: {"destination": "Yosemite", "dates": "next weekend", "activity": "backpacking"}

Example input: "Going camping"
Example output: {"destination": null, "dates": null, "activity": "camping"}

ONLY return the JSON object. No explanation, no markdown formatting, no code blocks, no extra text. Just the raw JSON."""
    
    return create_agent(
        agent_id="context-extractor-agent",
        name="Trip Context Extractor",
        description="Extracts destination, dates, and activity from user trip queries. Returns structured JSON only.",
        instructions=instructions,
        tool_ids=[]  # No tools needed - just parsing
    )


def create_response_parser_agent() -> Optional[str]:
    """Create the Response Parser agent that extracts structured data from trip plans."""
    instructions = """You extract structured data from trip planning responses. Return ONLY valid JSON, no other text.

Extract:
- products: Array of recommended products with name, price, category, and reason
- itinerary: Array of days with day number, title, distance, and activities
- safety_notes: Array of safety warnings and tips
- weather: Object with high, low, and conditions

JSON Schema:
{
  "products": [
    {"name": "Product Name", "price": 123.45, "category": "sleeping bag", "reason": "why recommended"}
  ],
  "itinerary": [
    {"day": 1, "title": "Day title", "distance": "4.7 miles", "activities": ["activity 1", "activity 2"]}
  ],
  "safety_notes": ["note 1", "note 2"],
  "weather": {"high": 45, "low": 28, "conditions": "Partly cloudy"}
}

Rules:
- Extract ALL products mentioned with their exact names and prices
- Parse prices as numbers (remove $ symbol)
- Include brand names in product names (e.g., "Summit Pro Apex Expedition 20 Sleeping Bag")
- If a field cannot be determined, use null or empty array
- ONLY return the JSON object. No explanation, no markdown, no extra text."""
    
    return create_agent(
        agent_id="response-parser-agent",
        name="Trip Response Parser",
        description="Extracts structured JSON from trip plan responses including products, itinerary, and safety info.",
        instructions=instructions,
        tool_ids=[]  # No tools needed - just parsing
    )


def create_itinerary_extractor_agent() -> Optional[str]:
    """Create the Itinerary Extractor agent that extracts structured day-by-day itinerary from trip plans."""
    instructions = """You extract a structured day-by-day itinerary from trip planning responses. Return ONLY valid JSON, no other text.

Extract the itinerary as an array of days. Each day should have:
- day: Day number (1, 2, 3, etc.)
- title: A descriptive title for the day (e.g., "Valley to Snow Creek", "Exploration Day", "Return Journey")
- activities: Array of specific activities/actions for that day

JSON Schema:
{
  "days": [
    {
      "day": 1,
      "title": "Day 1 Title",
      "activities": [
        "Start early from valley floor",
        "Gain elevation gradually with snowshoes",
        "Camp below treeline for wind protection"
      ]
    },
    {
      "day": 2,
      "title": "Day 2 Title",
      "activities": [
        "Practice winter camping skills",
        "Short radius exploration",
        "Return to established camp"
      ]
    }
  ]
}

Rules:
- Look for explicit day markers: "Day 1:", "Day 2:", "First day", "Second day", etc.
- Extract activities as individual items from bullet points, numbered lists, or sentences
- Each activity should be a complete, actionable item
- If the trip plan mentions a multi-day trip but doesn't break it down by days, infer logical day breaks based on the content
- If no day-by-day breakdown exists, create a single day entry with all activities
- ONLY return the JSON object. No explanation, no markdown code blocks, no extra text."""
    
    return create_agent(
        agent_id="itinerary-extractor-agent",
        name="Itinerary Extractor",
        description="Extracts structured day-by-day itinerary from trip plan responses. Returns JSON only.",
        instructions=instructions,
        tool_ids=[]  # No tools needed - just parsing
    )


def _swap_param_types(params: Dict, to_legacy: bool = True) -> Dict:
    """Swap param types between newer API format and legacy ES field types.
    
    Newer clusters accept: string, integer, float, boolean, date
    Older clusters accept: text, keyword, long, integer, double, float, boolean, date, object, nested
    """
    type_map = {"string": "keyword"} if to_legacy else {"keyword": "string"}
    swapped = {}
    for key, value in params.items():
        new_value = dict(value)
        if new_value.get("type") in type_map:
            new_value["type"] = type_map[new_value["type"]]
        swapped[key] = new_value
    return swapped


def create_esql_tool(name: str, query: str, description: str, params: Optional[Dict] = None) -> Optional[str]:
    """Create an ES|QL tool and return its ID. Deletes existing tool first.
    
    Handles API compatibility: tries newer param types (string) first,
    falls back to legacy ES field types (keyword) for older clusters.
    """
    global FAILURES
    url = f"{KIBANA_URL}/api/agent_builder/tools"
    
    # Generate a unique ID for the tool
    tool_id = f"tool-esql-{name.replace('_', '-')}"
    
    # Delete existing tool first (script is source of truth)
    delete_tool(tool_id)
    
    tool_config = {
        "id": tool_id,
        "type": "esql",
        "description": description,
        "configuration": {
            "query": query,
            "params": params or {}  # Required by API
        }
    }
    
    response = request_with_retry("POST", url, headers=HEADERS, json=tool_config)
    
    if response.status_code in [200, 201]:
        data = response.json()
        created_id = data.get("id") or data.get("tool_id") or tool_id
        print(f"✓ Created ES|QL tool: {name} (ID: {created_id})")
        return created_id
    elif response.status_code == 400 and params and "types that failed validation" in response.text:
        # Fallback: try legacy ES field types (keyword instead of string) for older clusters
        print(f"  ⚠ Retrying with legacy param types (keyword)...")
        legacy_params = _swap_param_types(params, to_legacy=True)
        tool_config["configuration"]["params"] = legacy_params
        
        response = request_with_retry("POST", url, headers=HEADERS, json=tool_config)
        if response.status_code in [200, 201]:
            data = response.json()
            created_id = data.get("id") or data.get("tool_id") or tool_id
            print(f"✓ Created ES|QL tool: {name} (ID: {created_id}) [legacy param types]")
            return created_id
    
    print(f"✗ Failed to create ES|QL tool (ID: {tool_id}): {response.status_code}")
    print(f"  Response: {response.text}")
    FAILURES += 1
    return None


def create_workflow_tool(name: str, workflow_id: str, description: str) -> Optional[str]:
    """Create a workflow tool and return its ID. Deletes existing tool first."""
    global FAILURES
    url = f"{KIBANA_URL}/api/agent_builder/tools"
    
    # Generate a unique ID for the tool
    tool_id = f"tool-workflow-{name.replace('_', '-')}"
    
    # Delete existing tool first (script is source of truth)
    delete_tool(tool_id)
    
    tool_config = {
        "id": tool_id,
        "type": "workflow",
        "description": description,
        "configuration": {
            "workflow_id": workflow_id
        }
    }
    
    response = request_with_retry("POST", url, headers=HEADERS, json=tool_config)
    
    if response.status_code in [200, 201]:
        data = response.json()
        created_id = data.get("id") or data.get("tool_id") or tool_id
        print(f"✓ Created workflow tool: {name} (ID: {created_id})")
        return created_id
    else:
        print(f"✗ Failed to create workflow tool (ID: {tool_id}): {response.status_code}")
        print(f"  Response: {response.text}")
        FAILURES += 1
        return None


def create_index_search_tool(name: str, index: str, description: str) -> Optional[str]:
    """Create an index search tool and return its ID. Deletes existing tool first."""
    global FAILURES
    url = f"{KIBANA_URL}/api/agent_builder/tools"
    
    # Generate a unique ID for the tool
    tool_id = f"tool-search-{name.replace('_', '-')}"
    
    # Delete existing tool first (script is source of truth)
    delete_tool(tool_id)
    
    tool_config = {
        "id": tool_id,
        "type": "index_search",
        "description": description,
        "configuration": {
            "pattern": index  # API expects 'pattern', not 'index'
        }
    }
    
    response = request_with_retry("POST", url, headers=HEADERS, json=tool_config)
    
    if response.status_code in [200, 201]:
        data = response.json()
        created_id = data.get("id") or data.get("tool_id") or tool_id
        print(f"✓ Created index search tool: {name} (ID: {created_id})")
        return created_id
    else:
        print(f"✗ Failed to create index search tool (ID: {tool_id}): {response.status_code}")
        print(f"  Response: {response.text}")
        FAILURES += 1
        return None


def delete_existing_workflows_by_name(workflow_name: str):
    """Delete all workflows with the given name."""
    url = f"{KIBANA_URL}/api/workflows/search"
    list_response = request_with_retry("POST", url, headers=HEADERS, json={"limit": 100, "page": 1, "query": ""})
    if list_response.status_code == 200:
        data = list_response.json()
        workflows = data.get("results", []) or data.get("data", [])
        for wf in workflows:
            if wf.get("name") == workflow_name:
                delete_workflow(wf.get("id"))

def deploy_workflow(workflow_yaml_path: str, mcp_url: Optional[str] = None) -> Optional[str]:
    """Deploy a workflow from YAML file. Deletes existing workflow first.
    
    Args:
        workflow_yaml_path: Path to the workflow YAML file
        mcp_url: Optional MCP server URL to substitute for the default Instruqt URL
    """
    global FAILURES
    import yaml
    
    # Read the raw YAML content as a string - API expects {"yaml": "..."}
    with open(workflow_yaml_path, 'r') as f:
        yaml_content = f.read()
    
    # Substitute MCP URL if provided (replace Instruqt default with standalone URL)
    if mcp_url and INSTRUQT_MCP_URL in yaml_content:
        yaml_content = yaml_content.replace(INSTRUQT_MCP_URL, mcp_url)
        print(f"  → Using MCP URL: {mcp_url}")
    
    # Also parse it to get the name for logging
    workflow_data = yaml.safe_load(yaml_content)
    workflow_name = workflow_data.get("name", "unknown")
    
    # Delete existing workflow(s) first (script is source of truth)
    delete_existing_workflows_by_name(workflow_name)
    
    url = f"{KIBANA_URL}/api/workflows"
    
    # API expects {"yaml": "<yaml_string>"}
    response = request_with_retry("POST", url, headers=HEADERS, json={"yaml": yaml_content})
    
    if response.status_code in [200, 201]:
        data = response.json()
        workflow_id = data.get("id") or data.get("workflow_id")
        print(f"✓ Deployed workflow: {workflow_name} (ID: {workflow_id})")
        return workflow_id
    else:
        print(f"✗ Failed to deploy workflow '{workflow_name}': {response.status_code}")
        print(f"  Response: {response.text}")
        FAILURES += 1
        return None


def main() -> int:
    """Main function. Returns number of failures (0 = success)."""
    import argparse
    parser = argparse.ArgumentParser(description="Create מצפן ציוד שטח Agents, Tools, and Workflows")
    parser.add_argument(
        "--skip-workflows",
        nargs="*",
        default=[],
        help="Workflow names to skip (e.g., get_customer_profile)"
    )
    parser.add_argument(
        "--skip-tools",
        nargs="*",
        default=[],
        help="Tool names to skip (e.g., tool-workflow-get-customer-profile)"
    )
    parser.add_argument(
        "--skip-agents",
        nargs="*",
        default=[],
        help="Agent names to skip (e.g., trip-planner-agent)"
    )
    parser.add_argument(
        "--mcp-url",
        default=None,
        help="MCP server URL to use in workflows (default: keeps Instruqt URL http://host-1:8002/mcp)"
    )
    args = parser.parse_args()
    
    print("Creating מצפן ציוד שטח Agents and Workflows...")
    print("=" * 60)
    if args.skip_workflows:
        print(f"Skipping workflows: {', '.join(args.skip_workflows)}")
    if args.skip_tools:
        print(f"Skipping tools: {', '.join(args.skip_tools)}")
    if args.skip_agents:
        print(f"Skipping agents: {', '.join(args.skip_agents)}")
    
    # Determine the correct path to config/workflows
    # Works whether run from repo root or from scripts directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)  # Go up one level from scripts/
    
    # Check multiple possible locations for workflow config
    possible_paths = [
        os.path.join(repo_root, "config", "workflows"),  # ../config/workflows (from scripts/)
        os.path.join(script_dir, "..", "config", "workflows"),  # Same, relative
        "config/workflows",  # From repo root
        "/opt/workshop-assets/config/workflows",  # Instruqt absolute path
    ]
    
    workflow_dir = None
    for path in possible_paths:
        if os.path.exists(path):
            workflow_dir = path
            print(f"Found workflow config at: {workflow_dir}")
            break
    
    if not workflow_dir:
        print("ERROR: Could not find workflow config directory!")
        print(f"Searched: {possible_paths}")
        return
    
    # Step 0: Delete main agents upfront so tools can be deleted
    # (tools referenced by agents return 409 on DELETE)
    print("\n0. Cleaning up existing agents...")
    for agent_id in ["trip-planner-agent", "wayfinder-search-agent", "trip-itinerary-agent",
                      "context-extractor-agent", "response-parser-agent", "itinerary-extractor-agent"]:
        delete_agent(agent_id)
    time.sleep(1)

    # Step 1: Create agents first (so workflows can reference them)
    print("\n1. Creating Agents...")
    context_extractor_id = create_context_extractor_agent()
    time.sleep(1)
    
    response_parser_id = create_response_parser_agent()
    time.sleep(1)
    
    itinerary_extractor_id = create_itinerary_extractor_agent()
    time.sleep(1)
    
    # Step 2: Deploy workflows (now that agents exist)
    print("\n2. Deploying Workflows...")
    if args.mcp_url:
        print(f"MCP URL override: {args.mcp_url}")
    
    workflows = {
        "check_trip_safety": f"{workflow_dir}/check_trip_safety.yaml",
        "get_customer_profile": f"{workflow_dir}/get_customer_profile.yaml",
        "get_user_affinity": f"{workflow_dir}/get_user_affinity.yaml",
        "extract_trip_entities": f"{workflow_dir}/extract_trip_entities.yaml"
    }
    
    workflow_ids = {}
    for name, path in workflows.items():
        if name in args.skip_workflows:
            print(f"⊘ Skipping workflow: {name}")
            continue
        if os.path.exists(path):
            workflow_id = deploy_workflow(path, mcp_url=args.mcp_url)
            if workflow_id:
                workflow_ids[name] = workflow_id
            time.sleep(1)  # Rate limiting
        else:
            print(f"⚠ Workflow file not found: {path}")
    
    # Step 3: Create tools (reference workflow IDs)
    print("\n3. Creating Tools...")
    tool_ids = []
    
    # Create ES|QL tool - query with user_id parameter
    esql_query = """FROM user-clickstream
| WHERE user_id == ?user_id AND meta_tags IS NOT NULL
| STATS count = COUNT(*) BY meta_tags
| SORT count DESC
| LIMIT 5"""
    esql_tool_id = create_esql_tool(
        name="get_user_affinity",
        query=esql_query,
        description="קבלת תגיות העדפות ציוד מהתנהגות גלישה של המשתמש",
        params={"user_id": {"type": "string", "description": "The user ID to look up browsing history for"}}
    )
    if esql_tool_id:
        tool_ids.append(esql_tool_id)
    time.sleep(1)
    
    # Create workflow tools
    workflow_tool_ids = {}
    for name, workflow_id in workflow_ids.items():
        # Skip creating workflow tool for get_user_affinity - we use the ES|QL tool instead
        # Also skip extract_trip_entities - it's used internally/manually, not as an agent tool
        if name in ["get_user_affinity", "extract_trip_entities"]:
            continue
        tool_name = f"tool-workflow-{name.replace('_', '-')}"
        if tool_name in args.skip_tools:
            print(f"⊘ Skipping tool: {tool_name}")
            continue
        descriptions = {
            "check_trip_safety": "קבלת תנאי מזג אוויר והתראות דרכים ליעד הטיול",
            "get_customer_profile": "אחזור פרופיל לקוח כולל היסטוריית רכישות ורמת נאמנות"
        }
        tool_id = create_workflow_tool(
            name=name,
            workflow_id=workflow_id,
            description=descriptions.get(name, f"Workflow: {name}")
        )
        if tool_id:
            workflow_tool_ids[name] = tool_id
            tool_ids.append(tool_id)
        time.sleep(1)
    
    # Create index search tool
    index_tool_id = create_index_search_tool(
        name="product_search",
        index="product-catalog",
        description="חיפוש בקטלוג המוצרים להמלצות ציוד"
    )
    if index_tool_id:
        tool_ids.append(index_tool_id)
    time.sleep(1)
    
    # Step 4: Create main agents (reference tool IDs)
    print("\n4. Creating Main Agents...")
    # Create wayfinder-search-agent (always created, not skipped)
    wayfinder_search_id = create_wayfinder_search_agent(tool_ids=tool_ids)
    time.sleep(1)
    
    trip_planner_id = None
    if "trip-planner-agent" not in args.skip_agents:
        trip_planner_id = create_trip_planner_agent(tool_ids=tool_ids)
        time.sleep(1)
    else:
        print("⊘ Skipping agent: trip-planner-agent")
    
    trip_itinerary_id = create_trip_itinerary_agent()
    time.sleep(1)
    
    print("\n" + "=" * 60)
    if FAILURES > 0:
        print(f"Setup FAILED with {FAILURES} error(s)!")
    else:
        print("Setup Complete!")
    print(f"Context Extractor Agent ID: {context_extractor_id}")
    print(f"Response Parser Agent ID: {response_parser_id}")
    print(f"Itinerary Extractor Agent ID: {itinerary_extractor_id}")
    print(f"Wayfinder Search Agent ID: {wayfinder_search_id}")
    print(f"Trip Planner Agent ID: {trip_planner_id}")
    print(f"Trip Itinerary Agent ID: {trip_itinerary_id}")
    print(f"Created {len(tool_ids)} tools")
    print("=" * 60)
    
    # Return proper exit code
    return FAILURES


if __name__ == "__main__":
    import sys
    failures = main()
    sys.exit(failures if failures else 0)

