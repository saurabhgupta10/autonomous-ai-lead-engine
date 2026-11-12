"""Acceptance Test Suite for Phase 6.
Executes real discovery across:
1. New York, USA - Restaurants (10)
2. London, UK - Restaurants (10)
3. Sydney, Australia - Salons (10)
4. Dubai, UAE - Cafes (10)
"""

import json
import logging
import time
from discovery.discovery_schemas import DiscoveryQuery
from discovery.discovery_service import DiscoveryService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("acceptance_tests")


def run_test_session(country: str, city: str, industry: str, limit: int = 10):
    service = DiscoveryService()
    query = DiscoveryQuery(
        country=country,
        city=city,
        industry=industry,
        max_results=limit,
    )

    t0 = time.time()
    logger.info(f"=== Starting Acceptance Test: {city}, {country} ({industry}, limit={limit}) ===")
    
    session_id = f"test_{city.lower().replace(' ', '_')}"
    service._lock.acquire()
    try:
        service._current_job = {
            "session_id": session_id,
            "status": "running",
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "finished_at": None,
            "error": None,
            "summary": {"stage": "querying_provider", "query": query.model_dump()},
            "results": [],
        }
        service._run_discovery_pipeline(session_id, query)
    finally:
        pass  # Lock is released inside _run_discovery_pipeline finally block

    duration = time.time() - t0
    status_data = service.get_status()
    summary = status_data.get("summary") or {}
    leads = service.get_latest_results()

    total = len(leads)
    with_website = sum(1 for l in leads if l.get("Website") or l.get("website"))
    without_website = total - with_website
    
    audited = sum(1 for l in leads if l.get("crawler_status") == "success" or l.get("Website Status") not in ("missing", None))
    high_priority = sum(1 for l in leads if (l.get("Priority") or l.get("priority")) == "High")
    medium_priority = sum(1 for l in leads if (l.get("Priority") or l.get("priority")) == "Medium")
    low_priority = sum(1 for l in leads if (l.get("Priority") or l.get("priority")) == "Low")

    osm_sources = sum(1 for l in leads if "openstreetmap.org" in (l.get("Source URL") or l.get("source_url") or ""))

    results = {
        "city": city,
        "country": country,
        "industry": industry,
        "session_id": session_id,
        "duration_seconds": round(duration, 2),
        "status": status_data.get("status"),
        "error": status_data.get("error"),
        "total_discovered": total,
        "with_website": with_website,
        "without_website": without_website,
        "audited_websites": audited,
        "lead_priorities": {
            "High": high_priority,
            "Medium": medium_priority,
            "Low": low_priority,
        },
        "verifiable_osm_sources": osm_sources,
        "duplicates_skipped": summary.get("duplicates_skipped", 0),
        "crm_synced": summary.get("crm_synced", 0),
        "crm_status": summary.get("crm_status"),
        "sample_leads": [
            {
                "name": l.get("Business Name") or l.get("name"),
                "category": l.get("Industry") or l.get("category"),
                "website": l.get("Website") or l.get("website"),
                "phone": l.get("Phone") or l.get("phone"),
                "priority": l.get("Priority") or l.get("priority"),
                "opportunity": l.get("AI Reasoning") or l.get("opportunity"),
                "source_url": l.get("Source URL") or l.get("source_url"),
            }
            for l in leads[:3]
        ],
    }

    logger.info(f"Finished {city}: {total} leads in {duration:.1f}s | With web: {with_website} | No web: {without_website} | High: {high_priority} | CRM Synced: {results['crm_synced']}")
    return results


def main():
    test_specs = [
        ("USA", "New York", "Restaurants", 10),
        ("UK", "London", "Restaurants", 10),
        ("Australia", "Sydney", "Beauty Salons", 10),
        ("UAE", "Dubai", "Cafes", 10),
    ]

    all_results = []
    for country, city, industry, limit in test_specs:
        try:
            res = run_test_session(country, city, industry, limit)
            all_results.append(res)
            time.sleep(2)
        except Exception as e:
            logger.error(f"Error testing {city}, {country}: {e}", exc_info=True)
            all_results.append({
                "city": city,
                "country": country,
                "industry": industry,
                "error": str(e),
            })

    output_file = "acceptance_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print("\n" + "=" * 60)
    print("ACCEPTANCE TESTS SUMMARY")
    print("=" * 60)
    for r in all_results:
        if r.get("error"):
            print(f"FAILED: {r['city']}, {r['country']} -> {r['error']}")
        else:
            print(f"PASSED: {r['city']}, {r['country']} -> Discovered: {r['total_discovered']}, Web: {r['with_website']}, No Web: {r['without_website']}, High: {r['lead_priorities']['High']}, CRM Synced: {r['crm_synced']}, Duplicates Skipped: {r['duplicates_skipped']} ({r.get('crm_status')})")
    print(f"\nDetailed results saved to {output_file}")


if __name__ == "__main__":
    main()
