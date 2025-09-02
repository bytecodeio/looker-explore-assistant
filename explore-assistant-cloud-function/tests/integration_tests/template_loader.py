"""
Template loader for golden queries and other required request data

Provides utilities to load and cache template data that must be included
in all API requests, such as golden queries which are required by the backend.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

# Template file paths
GOLDEN_QUERIES_TEMPLATE = Path(__file__).parent / "golden_queries_template.json"


class TemplateLoadError(Exception):
    """Raised when a template file cannot be loaded"""
    pass


@lru_cache(maxsize=None)
def load_golden_queries_template() -> Dict[str, Any]:
    """
    Load the golden queries template from file with caching
    
    The golden queries are required for all API requests and contain
    example queries, refinements, and explore entries that the backend
    uses for context and learning.
    
    Returns:
        Dictionary containing the golden queries structure
        
    Raises:
        TemplateLoadError: If the template file cannot be loaded
    """
    try:
        if not GOLDEN_QUERIES_TEMPLATE.exists():
            raise TemplateLoadError(
                f"Golden queries template not found at {GOLDEN_QUERIES_TEMPLATE}. "
                f"Run extract_templates.py to create it from sample data."
            )
        
        with open(GOLDEN_QUERIES_TEMPLATE, 'r', encoding='utf-8') as f:
            golden_queries = json.load(f)
        
        # Validate structure
        required_keys = ['exploreEntries', 'exploreGenerationExamples', 
                        'exploreRefinementExamples', 'exploreSamples']
        
        missing_keys = [key for key in required_keys if key not in golden_queries]
        if missing_keys:
            raise TemplateLoadError(
                f"Golden queries template missing required keys: {missing_keys}"
            )
        
        logger.info(f"✅ Loaded golden queries template with {len(golden_queries['exploreEntries'])} explore entries")
        return golden_queries
        
    except json.JSONDecodeError as e:
        raise TemplateLoadError(f"Invalid JSON in golden queries template: {e}")
    except Exception as e:
        raise TemplateLoadError(f"Failed to load golden queries template: {e}")


def get_template_statistics() -> Dict[str, Any]:
    """Get statistics about loaded templates"""
    try:
        golden_queries = load_golden_queries_template()
        
        stats = {
            "golden_queries": {
                "file_path": str(GOLDEN_QUERIES_TEMPLATE),
                "file_exists": GOLDEN_QUERIES_TEMPLATE.exists(),
                "explore_entries_count": len(golden_queries.get('exploreEntries', [])),
                "generation_examples_explores": list(golden_queries.get('exploreGenerationExamples', {}).keys()),
                "refinement_examples_explores": list(golden_queries.get('exploreRefinementExamples', {}).keys()),
                "samples_explores": list(golden_queries.get('exploreSamples', {}).keys()),
                "template_size_bytes": len(json.dumps(golden_queries)),
                "cached": True  # Since we're using @lru_cache
            }
        }
        
        return stats
        
    except TemplateLoadError as e:
        return {
            "golden_queries": {
                "file_path": str(GOLDEN_QUERIES_TEMPLATE),
                "file_exists": GOLDEN_QUERIES_TEMPLATE.exists(),
                "error": str(e),
                "cached": False
            }
        }


def validate_template_integrity() -> Dict[str, Any]:
    """
    Validate that templates are properly structured and complete
    
    Returns:
        Dictionary with validation results
    """
    results = {
        "overall_status": "unknown",
        "golden_queries": {"status": "unknown", "issues": []}
    }
    
    try:
        # Test golden queries template
        golden_queries = load_golden_queries_template()
        gq_issues = []
        
        # Check explore entries
        if not golden_queries.get('exploreEntries'):
            gq_issues.append("No exploreEntries found")
        else:
            entries = golden_queries['exploreEntries']
            if not isinstance(entries, list):
                gq_issues.append("exploreEntries should be a list")
            elif len(entries) == 0:
                gq_issues.append("exploreEntries is empty")
            else:
                # Check first entry structure
                first_entry = entries[0]
                required_entry_keys = ['golden_queries.explore_id', 'golden_queries.input', 'golden_queries.output']
                missing_entry_keys = [key for key in required_entry_keys if key not in first_entry]
                if missing_entry_keys:
                    gq_issues.append(f"Explore entry missing keys: {missing_entry_keys}")
        
        # Check generation examples
        if not golden_queries.get('exploreGenerationExamples'):
            gq_issues.append("No exploreGenerationExamples found")
        else:
            gen_examples = golden_queries['exploreGenerationExamples']
            if not isinstance(gen_examples, dict):
                gq_issues.append("exploreGenerationExamples should be a dict")
            elif len(gen_examples) == 0:
                gq_issues.append("exploreGenerationExamples is empty")
        
        results["golden_queries"]["status"] = "valid" if not gq_issues else "invalid"
        results["golden_queries"]["issues"] = gq_issues
        results["golden_queries"]["entries_count"] = len(golden_queries.get('exploreEntries', []))
        
    except TemplateLoadError as e:
        results["golden_queries"]["status"] = "error"
        results["golden_queries"]["issues"] = [str(e)]
    
    # Overall status
    all_statuses = [results["golden_queries"]["status"]]
    if all(status == "valid" for status in all_statuses):
        results["overall_status"] = "valid"
    elif any(status == "error" for status in all_statuses):
        results["overall_status"] = "error"
    else:
        results["overall_status"] = "invalid"
    
    return results


def clear_template_cache():
    """Clear the template cache to force reload on next access"""
    load_golden_queries_template.cache_clear()
    logger.info("🧹 Template cache cleared")


if __name__ == "__main__":
    # Test the template loader
    print("🧪 Testing template loader...")
    
    try:
        stats = get_template_statistics()
        print(f"📊 Template Statistics:")
        print(f"   Golden Queries: {stats['golden_queries']['explore_entries_count']} entries")
        print(f"   File Size: {stats['golden_queries']['template_size_bytes']:,} bytes")
        print(f"   Generation Examples: {stats['golden_queries']['generation_examples_explores']}")
        
        validation = validate_template_integrity()
        print(f"\n✅ Validation Status: {validation['overall_status']}")
        
        if validation['golden_queries']['issues']:
            print("❌ Issues found:")
            for issue in validation['golden_queries']['issues']:
                print(f"   • {issue}")
        else:
            print("✅ All templates valid!")
            
    except Exception as e:
        print(f"❌ Error testing templates: {e}")