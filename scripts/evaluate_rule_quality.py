#!/usr/bin/env python3
"""
Evaluate rule quality: adequacy, precision, false positive risk.

Analyzes generated SQL rules for:
1. Adequacy - do they match real spam patterns?
2. Quality - are they well-formed and specific?
3. False positive risk - will they ban legitimate messages?
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Dict, Any
import re


class RuleQualityEvaluator:
    """Evaluate rule quality and false positive risk."""
    
    # High-risk patterns that catch too much
    RISKY_PATTERNS = [
        r"%\b(if|for|on|in|at|to|of|the|a|an)\b%",  # Common words
        r"%\b(group|price|contact|service|message)\b%",  # Legitimate business terms
        r"%\b(verify|check|account|security)\b%",  # Legitimate security terms
        r"%\b(buy|sell|sale)\b%",  # Legitimate commerce
        r"%\b(job|work|salary|income)\b%",  # Legitimate job discussions
    ]
    
    # Safe patterns (specific spam indicators)
    SAFE_PATTERNS = [
        r"phishing-link\.org",
        r"fake-.*\.com",
        r"scam-.*\.net",
        r"spam-link\.com",
        r"suspended.*verify.*now",
        r"urgent.*verify.*account",
    ]
    
    def evaluate_rule(self, sql: str, description: str = "") -> Dict[str, Any]:
        """
        Evaluate single rule.
        
        Returns:
            {
                'adequacy': 'high|medium|low',
                'quality': 'high|medium|low',
                'false_positive_risk': 'low|medium|high',
                'issues': List[str],
                'recommendations': List[str]
            }
        """
        issues = []
        recommendations = []
        fp_risk = "low"
        adequacy = "medium"
        quality = "medium"
        
        sql_upper = sql.upper()
        
        # 1. Check for overly broad patterns
        if any(re.search(pattern, sql, re.IGNORECASE) for pattern in self.RISKY_PATTERNS):
            # Check if it's combined with other conditions (AND clause)
            if " AND " not in sql_upper and " OR " in sql_upper:
                # Multiple ORs without AND - might be too broad
                or_count = sql_upper.count(" OR ")
                if or_count > 5:
                    issues.append(f"Too many OR conditions ({or_count}) without AND - may catch legitimate messages")
                    fp_risk = "high"
                    recommendations.append("Add AND conditions to narrow the rule")
                elif or_count > 3:
                    fp_risk = "medium"
        
        # 2. Check for safe patterns (specific spam domains)
        if any(re.search(pattern, sql, re.IGNORECASE) for pattern in self.SAFE_PATTERNS):
            adequacy = "high"
            quality = "high"
            fp_risk = "low"
        
        # 3. Check for single keyword without context
        like_matches = re.findall(r"LIKE\s+'%([^%]+)%'", sql, re.IGNORECASE)
        if len(like_matches) == 1:
            keyword = like_matches[0].lower()
            # Check if it's a common word
            common_words = ['if', 'for', 'on', 'in', 'at', 'to', 'of', 'the', 'a', 'an', 'is', 'are', 'was', 'were']
            if keyword in common_words:
                issues.append(f"Single common word '{keyword}' - very high false positive risk")
                fp_risk = "high"
                adequacy = "low"
                recommendations.append("Add additional conditions or remove this rule")
        
        # 4. Check for phone number regex (can match legitimate contacts)
        if "REGEXP" in sql_upper and "phone" in sql.lower():
            issues.append("Phone number regex may match legitimate contact information")
            fp_risk = "medium"
            recommendations.append("Ensure phone numbers are in commercial spam context only")
        
        # 5. Check for very short patterns
        for match in like_matches:
            if len(match) < 3:
                issues.append(f"Very short pattern '{match}' - may cause false positives")
                fp_risk = "high" if fp_risk == "low" else fp_risk
        
        # 6. Check for AND conditions (good - more specific)
        if " AND " in sql_upper:
            quality = "high"
            if fp_risk == "medium":
                fp_risk = "low"  # AND conditions reduce risk
        
        # 7. Check for specific domains (very safe)
        domain_pattern = r"http[s]?://([^/\s]+)"
        domains = re.findall(domain_pattern, sql, re.IGNORECASE)
        if domains:
            # Check if domains are clearly spam
            spam_domains = ['phishing', 'fake', 'scam', 'spam']
            if any(spam_word in domain.lower() for domain in domains for spam_word in spam_domains):
                adequacy = "high"
                quality = "high"
                fp_risk = "low"
        
        # 8. Check rule structure
        if not sql_upper.startswith("SELECT"):
            issues.append("Rule doesn't start with SELECT - may be unsafe")
            quality = "low"
        
        # Check for SQL injection keywords (but ignore if in URL strings)
        # Only flag if UPDATE/DELETE/INSERT are SQL keywords, not part of URL strings
        sql_keywords = re.findall(r'\b(UPDATE|DELETE|INSERT|DROP|ALTER|CREATE)\b', sql_upper)
        if sql_keywords:
            # Check if they're in string literals (URLs) - that's OK
            in_strings = False
            for keyword in sql_keywords:
                # Check if keyword appears inside quotes (URL string)
                pattern = f"['\"].*{keyword}.*['\"]"
                if re.search(pattern, sql, re.IGNORECASE):
                    in_strings = True
                    break
            
            if not in_strings:
                issues.append(f"Rule contains SQL keywords {sql_keywords} - UNSAFE!")
                fp_risk = "critical"
                quality = "low"
        
        return {
            'adequacy': adequacy,
            'quality': quality,
            'false_positive_risk': fp_risk,
            'issues': issues,
            'recommendations': recommendations,
        }
    
    def evaluate_all_rules(self, rules: List[str]) -> Dict[str, Any]:
        """Evaluate all rules and generate summary."""
        results = []
        high_risk_count = 0
        medium_risk_count = 0
        low_risk_count = 0
        
        for i, sql in enumerate(rules, 1):
            result = self.evaluate_rule(sql)
            result['rule_id'] = i
            result['sql'] = sql[:100] + "..." if len(sql) > 100 else sql
            results.append(result)
            
            if result['false_positive_risk'] == 'high' or result['false_positive_risk'] == 'critical':
                high_risk_count += 1
            elif result['false_positive_risk'] == 'medium':
                medium_risk_count += 1
            else:
                low_risk_count += 1
        
        return {
            'total_rules': len(rules),
            'risk_distribution': {
                'low': low_risk_count,
                'medium': medium_risk_count,
                'high': high_risk_count,
            },
            'rules': results,
            'summary': {
                'safe_for_production': low_risk_count,
                'needs_review': medium_risk_count,
                'should_not_use': high_risk_count,
            }
        }


def main():
    """Evaluate rules from SQL file."""
    sql_file = Path("patas_analysis_rules.sql")
    
    if not sql_file.exists():
        print(f"❌ File not found: {sql_file}")
        return
    
    # Read SQL rules
    with open(sql_file, 'r') as f:
        content = f.read()
    
    # Extract SQL statements (lines that start with SELECT)
    rules = []
    for line in content.split('\n'):
        line = line.strip()
        if line and line.upper().startswith('SELECT'):
            rules.append(line)
    
    if not rules:
        print("❌ No SQL rules found in file")
        return
    
    print(f"📊 Evaluating {len(rules)} rules...\n")
    
    evaluator = RuleQualityEvaluator()
    results = evaluator.evaluate_all_rules(rules)
    
    # Print summary
    print("=" * 60)
    print("📋 RULE QUALITY EVALUATION SUMMARY")
    print("=" * 60)
    print(f"\nTotal Rules: {results['total_rules']}")
    print(f"\nFalse Positive Risk Distribution:")
    print(f"  ✅ Low Risk (Safe): {results['risk_distribution']['low']}")
    print(f"  ⚠️  Medium Risk (Review): {results['risk_distribution']['medium']}")
    print(f"  ❌ High Risk (Avoid): {results['risk_distribution']['high']}")
    
    # Print high-risk rules
    high_risk_rules = [r for r in results['rules'] if r['false_positive_risk'] in ['high', 'critical']]
    if high_risk_rules:
        print(f"\n⚠️  HIGH RISK RULES ({len(high_risk_rules)}):")
        print("-" * 60)
        for rule in high_risk_rules[:10]:  # Show first 10
            print(f"\nRule {rule['rule_id']}:")
            print(f"  Risk: {rule['false_positive_risk'].upper()}")
            print(f"  SQL: {rule['sql']}")
            if rule['issues']:
                print(f"  Issues:")
                for issue in rule['issues']:
                    print(f"    - {issue}")
            if rule['recommendations']:
                print(f"  Recommendations:")
                for rec in rule['recommendations']:
                    print(f"    - {rec}")
    
    # Print medium-risk rules summary
    medium_risk_rules = [r for r in results['rules'] if r['false_positive_risk'] == 'medium']
    if medium_risk_rules:
        print(f"\n⚠️  MEDIUM RISK RULES ({len(medium_risk_rules)}):")
        print("-" * 60)
        for rule in medium_risk_rules[:5]:  # Show first 5
            print(f"\nRule {rule['rule_id']}: {rule['sql'][:80]}...")
            if rule['issues']:
                print(f"  Issues: {', '.join(rule['issues'][:2])}")
    
    # Overall assessment
    print("\n" + "=" * 60)
    print("📊 OVERALL ASSESSMENT")
    print("=" * 60)
    
    safe_percentage = (results['risk_distribution']['low'] / results['total_rules']) * 100
    if safe_percentage >= 80:
        assessment = "✅ EXCELLENT - Most rules are safe for production"
    elif safe_percentage >= 60:
        assessment = "✅ GOOD - Majority of rules are safe, some need review"
    elif safe_percentage >= 40:
        assessment = "⚠️  MODERATE - Many rules need review before production use"
    else:
        assessment = "❌ POOR - Most rules have high false positive risk"
    
    print(f"\n{assessment}")
    print(f"\nSafe for production: {results['summary']['safe_for_production']}/{results['total_rules']} ({safe_percentage:.1f}%)")
    print(f"Needs review: {results['summary']['needs_review']}/{results['total_rules']}")
    print(f"Should not use: {results['summary']['should_not_use']}/{results['total_rules']}")
    
    # Recommendations
    print("\n" + "=" * 60)
    print("💡 RECOMMENDATIONS")
    print("=" * 60)
    
    if results['summary']['should_not_use'] > 0:
        print("\n❌ CRITICAL:")
        print("  - Remove or fix high-risk rules before production deployment")
        print("  - Use shadow evaluation to test rules on historical data")
        print("  - Consider using 'conservative' profile (precision >= 0.95)")
    
    if results['summary']['needs_review'] > 0:
        print("\n⚠️  REVIEW NEEDED:")
        print("  - Test medium-risk rules in shadow mode first")
        print("  - Monitor false positive rate after deployment")
        print("  - Add additional AND conditions to narrow rules")
    
    if results['summary']['safe_for_production'] > 0:
        print("\n✅ SAFE RULES:")
        print("  - Low-risk rules can be used with 'conservative' profile")
        print("  - Still recommend shadow evaluation before active deployment")
        print("  - Monitor precision metrics after activation")


if __name__ == "__main__":
    main()

