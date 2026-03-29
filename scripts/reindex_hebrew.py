#!/usr/bin/env python3
"""
Self-contained script to reindex Hebrew products into Elasticsearch.
Handles: mapping fix (ELSER -> E5 multilingual), index recreation, bulk indexing.
No external dependencies beyond elasticsearch (pip install elasticsearch).
"""
import json
import os
import sys
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Try multiple env var sources
ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:30920")
ES_APIKEY = os.getenv("ELASTICSEARCH_APIKEY", os.getenv("ELASTIC_API_KEY", ""))

if not ES_APIKEY:
    print("ERROR: ELASTICSEARCH_APIKEY not set. Run: source /opt/workshop-assets/.env")
    sys.exit(1)

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

es = Elasticsearch([ES_URL], api_key=ES_APIKEY, request_timeout=120)

PRODUCTS_PATH = os.getenv("PRODUCTS_PATH", "/opt/workshop-assets/generated_products/products.json")
REVIEWS_PATH = os.getenv("REVIEWS_PATH", "/opt/workshop-assets/generated_products/reviews.json")

OLD_INFERENCE = ".elser-2-elastic"
NEW_INFERENCE = ".multilingual-e5-small-elasticsearch"


def fix_and_recreate_index(index_name):
    """Get mapping, replace ELSER with E5, delete and recreate index."""
    print(f"\n=== Fixing index: {index_name} ===")

    # Get current mapping
    try:
        mapping_resp = es.indices.get_mapping(index=index_name)
    except Exception as e:
        print(f"  Could not get mapping for {index_name}: {e}")
        return False

    # Convert to string, replace inference ID, convert back
    mapping_str = json.dumps(mapping_resp.body)
    if OLD_INFERENCE not in mapping_str:
        print(f"  No {OLD_INFERENCE} found in mapping, skipping fix")
        return True

    mapping_str = mapping_str.replace(OLD_INFERENCE, NEW_INFERENCE)
    mapping_data = json.loads(mapping_str)

    # Extract just the mappings portion
    idx_name = list(mapping_data.keys())[0]
    mappings = mapping_data[idx_name]["mappings"]

    # Remove model_settings from semantic_text fields (old ELSER settings conflict with E5)
    def strip_model_settings(obj):
        if isinstance(obj, dict):
            obj.pop("model_settings", None)
            for v in obj.values():
                strip_model_settings(v)
        elif isinstance(obj, list):
            for item in obj:
                strip_model_settings(item)

    strip_model_settings(mappings)

    # Delete index
    print(f"  Deleting {index_name}...")
    es.indices.delete(index=index_name, ignore=[404])
    time.sleep(1)

    # Recreate with fixed mapping
    print(f"  Creating {index_name} with {NEW_INFERENCE}...")
    es.indices.create(index=index_name, mappings=mappings)
    print(f"  ✓ Index {index_name} recreated")
    return True


def index_products(products_path):
    """Bulk index products from JSON file."""
    if not os.path.exists(products_path):
        print(f"  Products file not found: {products_path}")
        return

    with open(products_path, "r", encoding="utf-8") as f:
        products = json.load(f)

    def gen():
        for p in products:
            yield {"_index": "product-catalog", "_id": p["id"], "_source": p}

    print(f"  Indexing {len(products)} products...")
    success, failed = bulk(es, gen(), raise_on_error=False)
    if failed:
        print(f"  WARNING: {len(failed)} failed")
        for item in failed[:3]:
            print(f"    {item}")
    else:
        print(f"  ✓ {success} products indexed")

    es.indices.refresh(index="product-catalog")

    # Wait for semantic_text embeddings to be generated (async inference)
    print("  Waiting for semantic embeddings to complete...")
    for attempt in range(30):
        try:
            # Try a semantic query — if embeddings aren't ready, it will fail or return 0
            resp = es.search(
                index="product-catalog",
                size=1,
                query={"semantic": {"field": "description.semantic", "query": "אוהל"}},
            )
            hits = resp["hits"]["total"]["value"]
            if hits > 0:
                print(f"  ✓ Semantic embeddings ready ({hits} results for test query)")
                break
        except Exception as e:
            pass
        if attempt < 29:
            time.sleep(5)
    else:
        print("  ⚠️ Semantic embeddings may not be fully ready (hybrid search might be slow initially)")


def index_reviews(reviews_path):
    """Bulk index reviews from JSON file."""
    if not os.path.exists(reviews_path):
        print(f"  Reviews file not found: {reviews_path}")
        return

    with open(reviews_path, "r", encoding="utf-8") as f:
        reviews = json.load(f)

    def gen():
        for r in reviews:
            yield {"_index": "product-reviews", "_id": r["id"], "_source": r}

    print(f"  Indexing {len(reviews)} reviews...")
    success, failed = bulk(es, gen(), raise_on_error=False)
    if failed:
        print(f"  WARNING: {len(failed)} failed")
        for item in failed[:3]:
            print(f"    {item}")
    else:
        print(f"  ✓ {success} reviews indexed")

    es.indices.refresh(index="product-reviews")


TAG_MAP = {
    "expedition": "משלחת",
    "family": "משפחתי",
    "professional": "מקצועי",
    "budget": "חסכוני",
    "ultralight": "אולטרלייט",
    "sustainable": "ירוק",
}


def translate_clickstream_tags():
    """Translate meta_tags in user-clickstream index from English to Hebrew.
    Uses a single painless script to translate ALL tags in one pass,
    avoiding version conflicts from sequential per-tag updates.
    """
    print("\n=== Translating clickstream meta_tags ===")

    # Single painless script that translates all tags at once
    resp = es.update_by_query(
        index="user-clickstream",
        query={"match_all": {}},
        script={
            "source": """
                if (ctx._source.meta_tags != null) {
                    for (int i = 0; i < ctx._source.meta_tags.size(); i++) {
                        String tag = ctx._source.meta_tags[i];
                        if (params.tag_map.containsKey(tag)) {
                            ctx._source.meta_tags[i] = params.tag_map.get(tag);
                        }
                    }
                }
            """,
            "params": {"tag_map": TAG_MAP},
        },
        conflicts="proceed",
        refresh=True,
    )
    updated = resp.get("updated", 0)
    print(f"  Translated tags in {updated} docs")
    print("  ✓ Clickstream tags translated")


def verify():
    """Check first product title."""
    resp = es.search(index="product-catalog", size=1, query={"match_all": {}})
    hits = resp["hits"]["hits"]
    if hits:
        title = hits[0]["_source"]["title"]
        print(f"\n✓ Verification - first product: {title}")
        return "א" in title or "ב" in title or "ג" in title or "ה" in title
    else:
        print("\n✗ No products found!")
        return False


def main():
    print(f"ES URL: {ES_URL}")
    print(f"Products: {PRODUCTS_PATH}")
    print(f"Replacing {OLD_INFERENCE} -> {NEW_INFERENCE}")

    # Fix product-catalog
    if fix_and_recreate_index("product-catalog"):
        index_products(PRODUCTS_PATH)

    # Fix product-reviews
    if os.path.exists(REVIEWS_PATH):
        if fix_and_recreate_index("product-reviews"):
            index_reviews(REVIEWS_PATH)

    # Translate clickstream tags
    translate_clickstream_tags()

    # Verify
    is_hebrew = verify()
    if is_hebrew:
        print("\n🎉 Hebrew products successfully indexed!")
    else:
        print("\n⚠️  Products may not be in Hebrew. Check the output above.")


if __name__ == "__main__":
    main()
