# PATAS Core - Usage Examples

Comprehensive examples for using PATAS Core via CLI, API, and Telegram integration.

---

## Table of Contents

1. [CLI Usage Examples](#cli-usage-examples)
2. [API Usage Examples](#api-usage-examples)
3. [Telegram Integration Examples](#telegram-integration-examples)
4. [Complete Workflow Examples](#complete-workflow-examples)

---

## CLI Usage Examples

### Basic Workflow

#### 1. Ingest Messages from Logs

```bash
# Ingest from Telegram logs (last 7 days)
patas ingest-logs --source=telegram --since-days=7

# Ingest from CSV file
patas ingest-logs --source=csv --input=spam_logs.csv

# Ingest from JSON file
patas ingest-logs --source=json --input=messages.json
```

#### 2. Discover Patterns

```bash
# Run pattern mining on all messages
patas mine-patterns

# Run with specific time range
patas mine-patterns --since-days=30

# Run with custom configuration
patas mine-patterns --min-cluster-size=5 --similarity-threshold=0.85
```

#### 3. Evaluate Rules in Shadow Mode

```bash
# Evaluate all shadow rules
patas eval-rules

# Evaluate specific rule
patas eval-rules --rule-id=RULE_123

# Evaluate with custom time period
patas eval-rules --since-days=14
```

#### 4. Promote Rules to Active

```bash
# Promote rules using Conservative profile
patas promote-rules --profile=conservative

# Promote rules using Balanced profile
patas promote-rules --profile=balanced

# Promote with custom thresholds
patas promote-rules --min-precision=0.98 --max-ham-rate=0.01
```

#### 5. Safety Evaluation

```bash
# Run safety evaluation before deployment
patas safety-eval

# Run with specific profile
patas safety-eval --profile=conservative

# Generate detailed report
patas safety-eval --output=./safety_report.json
```

#### 6. Explain a Rule

```bash
# Get detailed explanation of a rule
patas explain-rule --id=RULE_123

# With more examples
patas explain-rule --id=RULE_123 --max-examples=10
```

### Advanced CLI Usage

#### Batch Processing

```bash
# Process multiple CSV files
for file in logs/*.csv; do
    patas ingest-logs --source=csv --input="$file"
done

# Run pattern mining after each batch
patas mine-patterns
```

#### Export Rules

```bash
# Export active rules as SQL
patas export-rules --backend=sql --output=rules.sql

# Export as ROL (Rule Object Language)
patas export-rules --backend=rol --output=rules.rol

# Export only Conservative profile rules
patas export-rules --profile=conservative --output=conservative_rules.sql
```

---

## API Usage Examples

### Python Examples

#### 1. Basic Health Check

```python
import requests

# Health check
response = requests.get("http://localhost:8000/api/v1/health")
print(response.json())
# Output: {"status": "ok", "version": "2.0.0", "core_ready": True}
```

#### 2. Ingest Messages

```python
import requests
from datetime import datetime, timezone

# Prepare messages
messages = [
    {
        "id": "msg_001",
        "text": "Buy now! http://spam.com",
        "is_spam": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "sender": "user123",
            "source": "chat456",
            "country": "US"
        }
    },
    {
        "id": "msg_002",
        "text": "Click here: http://spam.com",
        "is_spam": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "sender": "user456",
            "source": "chat789",
            "country": "US"
        }
    }
]

# Ingest messages
response = requests.post(
    "http://localhost:8000/api/v1/messages/ingest",
    json=messages
)

result = response.json()
print(f"Ingested {result['ingested_count']} messages")
```

#### 3. Pattern Mining

```python
import requests

# Run pattern mining
response = requests.post(
    "http://localhost:8000/api/v1/patterns/mine",
    json={
        "since_days": 7,
        "min_cluster_size": 5
    }
)

result = response.json()
print(f"Discovered {result['patterns_created']} patterns")
print(f"Created {result['rules_created']} rules")
```

#### 4. List Patterns

```python
import requests

# List all patterns
response = requests.get("http://localhost:8000/api/v1/patterns")

patterns = response.json()
for pattern in patterns:
    print(f"Pattern {pattern['id']}: {pattern['description']}")
    print(f"  Type: {pattern['type']}")
    print(f"  Examples: {pattern['examples'][:2]}")

# List with pagination
response = requests.get(
    "http://localhost:8000/api/v1/patterns",
    params={"limit": 10, "offset": 0}
)
```

#### 5. Evaluate Rules

```python
import requests

# Evaluate shadow rules
response = requests.post(
    "http://localhost:8000/api/v1/rules/eval-shadow",
    json={
        "rule_ids": None,  # Evaluate all shadow rules
        "since_days": 14
    }
)

result = response.json()
print(f"Evaluated {result['evaluated_count']} rules")

for evaluation in result['evaluations']:
    rule_id = evaluation['rule_id']
    precision = evaluation['precision']
    coverage = evaluation['coverage']
    print(f"Rule {rule_id}: precision={precision:.3f}, coverage={coverage:.3f}")
```

#### 6. Promote Rules

```python
import requests

# Promote rules using Conservative profile
response = requests.post(
    "http://localhost:8000/api/v1/rules/promote",
    json={
        "profile": "conservative",
        "auto_export": True
    }
)

result = response.json()
print(f"Promoted {result['promoted_count']} rules")
print(f"Deprecated {result['deprecated_count']} rules")
```

#### 7. Batch Analysis

```python
import requests

# Complete workflow in one request
messages = [
    {
        "id": "msg_001",
        "text": "Buy now! http://spam.com",
        "is_spam": True,
        "meta": {"sender": "user123"}
    },
    {
        "id": "msg_002",
        "text": "Click here: http://spam.com",
        "is_spam": True,
        "meta": {"sender": "user456"}
    }
]

response = requests.post(
    "http://localhost:8000/api/v1/analyze",
    json={
        "messages": messages,
        "run_mining": True,
        "run_evaluation": True,
        "export_backend": "sql",
        "profile": "conservative",  # Filter rules by precision >= 0.95
        "include_explanations": True,  # Include rule explanations
        "group_by_pattern": False,  # Group rules under patterns
    }
)

result = response.json()

# Process results
print(f"Discovered {len(result['patterns'])} patterns")
print(f"Generated {len(result['rules'])} rules")

# Print system information
if result.get('system_info'):
    print(f"\nHow it works: {result['system_info']['how_it_works']}")

# Print patterns with SQL
for pattern in result['patterns']:
    print(f"\nPattern: {pattern['description']}")
    print(f"  Group size: {pattern['group_size']}")
    print(f"  SQL: {pattern['sql_query']}")

# Print rules with explanations and risk assessment
for rule in result['rules']:
    print(f"\nRule {rule['id']}:")
    if rule.get('explanation'):
        print(f"  Explanation: {rule['explanation']}")
    if rule.get('risk_assessment'):
        print(f"  Risk level: {rule['risk_assessment']['risk_level']}")
        if rule['risk_assessment']['risk_warnings']:
            print(f"  Warnings: {', '.join(rule['risk_assessment']['risk_warnings'])}")

# Export rules
if result.get('export'):
    print(f"\nExported SQL Rules:\n{result['export']}")
```

### JavaScript/TypeScript Examples

#### 1. Basic Health Check

```javascript
const response = await fetch('http://localhost:8000/api/v1/health');
const data = await response.json();
console.log(data);
// Output: { status: "ok", version: "2.0.0", core_ready: true }
```

#### 2. Ingest Messages

```javascript
const messages = [
  {
    id: 'msg_001',
    text: 'Buy now! http://spam.com',
    is_spam: true,
    timestamp: new Date().toISOString(),
    meta: {
      sender: 'user123',
      source: 'chat456',
      country: 'US'
    }
  }
];

const response = await fetch('http://localhost:8000/api/v1/messages/ingest', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(messages)
});

const result = await response.json();
console.log(`Ingested ${result.ingested_count} messages`);
```

#### 3. Batch Analysis

```javascript
const messages = [
  {
    id: 'msg_001',
    text: 'Buy now! http://spam.com',
    is_spam: true,
    meta: { sender: 'user123' }
  }
];

const response = await fetch('http://localhost:8000/api/v1/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    messages,
    run_mining: true,
    run_evaluation: true,
    export_backend: 'sql'
  })
});

const result = await response.json();
console.log(`Discovered ${result.patterns.length} patterns`);

result.patterns.forEach(pattern => {
  console.log(`Pattern: ${pattern.description}`);
  console.log(`  SQL: ${pattern.sql_query}`);
});
```

### cURL Examples

#### 1. Health Check

```bash
curl http://localhost:8000/api/v1/health
```

#### 2. Ingest Messages

```bash
curl -X POST http://localhost:8000/api/v1/messages/ingest \
  -H "Content-Type: application/json" \
  -d '[
    {
      "id": "msg_001",
      "text": "Buy now! http://spam.com",
      "is_spam": true,
      "meta": {"sender": "user123"}
    }
  ]'
```

#### 3. Pattern Mining

```bash
curl -X POST http://localhost:8000/api/v1/patterns/mine \
  -H "Content-Type: application/json" \
  -d '{"since_days": 7}'
```

#### 4. Batch Analysis

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "id": "msg_001",
        "text": "Buy now! http://spam.com",
        "is_spam": true
      }
    ],
    "run_mining": true,
    "run_evaluation": true
  }'
```

---

## Telegram Integration Examples

### Using CLI

#### 1. Run PoC (Proof of Concept)

```bash
# Basic PoC
patas-tg poc --input=examples/sample_telegram_logs.jsonl --out=./report

# With specific profile
patas-tg poc --input=logs.jsonl --out=./report --profile=CONSERVATIVE

# With custom configuration
patas-tg poc --input=logs.jsonl --out=./report --profile=BALANCED --min-precision=0.95
```

#### 2. Convert Telegram Logs

```python
from telegram_integration.adapters import TelegramMessageAdapter
from telegram_integration.backends import TelegramRuleBackend

# Convert Telegram log format to PATAS Message
adapter = TelegramMessageAdapter()
telegram_log = {
    "message_id": "12345",
    "message_content": "Buy now! http://spam.com",
    "sender": "user123",
    "source": "chat456",
    "label_spam": True
}

message = adapter.convert(telegram_log)
print(f"Converted: {message.text}")
```

#### 3. Export Rules for Telegram

```python
from telegram_integration.backends import TelegramRuleBackend

# Export PATAS rules to Telegram format
backend = TelegramRuleBackend()

# Get rules from PATAS
rules = [...]  # Your rules from PATAS

# Export to Telegram format
telegram_rules = backend.export_rules(rules)
print(telegram_rules)
```

### Using API with Telegram Data

```python
import requests
from telegram_integration.adapters import TelegramMessageAdapter

# Load Telegram logs
adapter = TelegramMessageAdapter()
telegram_logs = [
    {
        "message_id": "12345",
        "message_content": "Buy now! http://spam.com",
        "sender": "user123",
        "source": "chat456",
        "label_spam": True
    }
]

# Convert to PATAS format
messages = [adapter.convert(log) for log in telegram_logs]

# Send to API
api_messages = [
    {
        "id": msg.external_id,
        "text": msg.text,
        "is_spam": msg.is_spam,
        "meta": msg.meta or {}
    }
    for msg in messages
]

response = requests.post(
    "http://localhost:8000/api/v1/analyze",
    json={
        "messages": api_messages,
        "run_mining": True,
        "run_evaluation": True
    }
)

result = response.json()
print(f"Discovered {len(result['patterns'])} patterns")
```

---

## Complete Workflow Examples

### Example 1: Full Pipeline from Logs to Production

```python
import requests
from datetime import datetime, timezone

# Step 1: Ingest historical logs
messages = load_messages_from_logs()  # Your function
response = requests.post(
    "http://localhost:8000/api/v1/messages/ingest",
    json=messages
)
print(f"Step 1: Ingested {response.json()['ingested_count']} messages")

# Step 2: Discover patterns
response = requests.post(
    "http://localhost:8000/api/v1/patterns/mine",
    json={"since_days": 30}
)
result = response.json()
print(f"Step 2: Discovered {result['patterns_created']} patterns")

# Step 3: Evaluate rules
response = requests.post(
    "http://localhost:8000/api/v1/rules/eval-shadow",
    json={"since_days": 14}
)
result = response.json()
print(f"Step 3: Evaluated {result['evaluated_count']} rules")

# Step 4: Review evaluation results
response = requests.get(
    "http://localhost:8000/api/v1/rules",
    params={"status": "shadow", "include_evaluation": True}
)
rules = response.json()
for rule in rules:
    if rule['evaluation']:
        precision = rule['evaluation']['precision']
        if precision >= 0.98:
            print(f"Rule {rule['id']}: precision={precision:.3f} (ready for promotion)")

# Step 5: Promote safe rules
response = requests.post(
    "http://localhost:8000/api/v1/rules/promote",
    json={"profile": "conservative"}
)
result = response.json()
print(f"Step 5: Promoted {result['promoted_count']} rules")

# Step 6: Export rules for deployment
response = requests.get(
    "http://localhost:8000/api/v1/rules/export",
    params={"backend": "sql"}
)
rules_sql = response.text
print(f"Step 6: Exported {len(rules_sql.split(';'))} SQL rules")
```

### Example 2: Continuous Monitoring Workflow

```python
import requests
import time
from datetime import datetime, timedelta, timezone

def continuous_monitoring():
    """Continuous monitoring workflow."""
    while True:
        # Ingest new messages (last hour)
        since_time = datetime.now(timezone.utc) - timedelta(hours=1)
        messages = get_new_messages(since_time)  # Your function
        
        if messages:
            # Ingest
            requests.post(
                "http://localhost:8000/api/v1/messages/ingest",
                json=messages
            )
            
            # Run pattern mining on new data
            requests.post(
                "http://localhost:8000/api/v1/patterns/mine",
                json={"since_days": 1}
            )
            
            # Evaluate new rules
            requests.post(
                "http://localhost:8000/api/v1/rules/eval-shadow"
            )
            
            # Check for rules ready for promotion
            response = requests.get(
                "http://localhost:8000/api/v1/rules",
                params={"status": "shadow", "include_evaluation": True}
            )
            rules = response.json()
            
            safe_rules = [
                r for r in rules
                if r.get('evaluation') and r['evaluation']['precision'] >= 0.98
            ]
            
            if safe_rules:
                # Promote safe rules
                requests.post(
                    "http://localhost:8000/api/v1/rules/promote",
                    json={"profile": "conservative"}
                )
                print(f"Promoted {len(safe_rules)} safe rules")
        
        # Wait before next iteration
        time.sleep(3600)  # 1 hour
```

### Example 3: Batch Analysis

```python
import requests

def analyze_batch(messages, export_format="sql"):
    """
    Analyze a batch of messages and return patterns/rules.
    
    Suitable for batch processing use cases.
    """
    response = requests.post(
        "http://localhost:8000/api/v1/analyze",
        json={
            "messages": messages,
            "run_mining": True,
            "run_evaluation": True,
            "export_backend": export_format
        }
    )
    
    if response.status_code != 200:
        raise Exception(f"API error: {response.text}")
    
    result = response.json()
    
    return {
        "patterns": result["patterns"],
        "rules": result["rules"],
        "export": result.get("export"),
        "metrics": {
            "patterns_count": len(result["patterns"]),
            "rules_count": len(result["rules"]),
            "processing_time": result.get("processing_time", 0)
        }
    }

# Usage
messages = [
    {
        "id": "msg_001",
        "text": "Buy now! http://spam.com",
        "is_spam": True,
        "meta": {"sender": "user123"}
    }
]

result = analyze_batch(messages, export_format="sql")
print(f"Discovered {result['metrics']['patterns_count']} patterns")
print(f"Generated {result['metrics']['rules_count']} rules")
```

---

## Error Handling Examples

### Python with Error Handling

```python
import requests
from requests.exceptions import RequestException

def safe_api_call(url, method="GET", json_data=None):
    """Make API call with error handling."""
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=json_data)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error: {e}")
        print(f"Response: {e.response.text}")
        return None
    
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return None

# Usage
result = safe_api_call(
    "http://localhost:8000/api/v1/health"
)
if result:
    print(f"API status: {result['status']}")
```

---

## Best Practices

1. **Always use Conservative profile for production**
   ```python
   # Good
   requests.post(
       "http://localhost:8000/api/v1/rules/promote",
       json={"profile": "conservative"}
   )
   ```

2. **Run safety evaluation before deployment**
   ```bash
   patas safety-eval --profile=conservative
   ```

3. **Monitor rule performance**
   ```python
   # Check evaluation metrics regularly
   response = requests.get(
       "http://localhost:8000/api/v1/rules",
       params={"status": "active", "include_evaluation": True}
   )
   ```

4. **Use batch analysis for small datasets**
   ```python
   # For < 10,000 messages
   requests.post("http://localhost:8000/api/v1/analyze", ...)
   ```

5. **Use separate endpoints for large datasets**
   ```python
   # For > 10,000 messages
   requests.post("http://localhost:8000/api/v1/messages/ingest", ...)
   requests.post("http://localhost:8000/api/v1/patterns/mine", ...)
   ```

---

**For more information, see:**
- [API Reference](https://github.com/kiku-jw/PATAS-core/wiki/API-Reference)
- [Quick Start Guide](https://github.com/kiku-jw/PATAS-core/wiki/Quick-Start)
- [Configuration](https://github.com/kiku-jw/PATAS-core/wiki/Configuration)






