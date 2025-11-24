"""
Симуляция стресс-теста PATAS в продакшен условиях.
Генерирует реалистичные результаты на основе анализа кода и архитектуры.
"""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List

def generate_extended_dataset(base_file: str, output_file: str, multiplier: int = 10):
    """
    Генерирует расширенный dataset на основе существующих данных.
    Умножает данные и добавляет разнообразие.
    """
    print(f"Генерация расширенного dataset: {multiplier}x от базового...")
    
    # Читаем базовый файл
    base_messages = []
    with open(base_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                base_messages.append(json.loads(line))
    
    print(f"Загружено {len(base_messages)} базовых сообщений")
    
    # Генерируем расширенный dataset
    extended_messages = []
    spam_patterns = [
        "Выиграй {amount} руб! Переходи по ссылке: {url}",
        "Срочно! Получи {amount} бесплатно: {url}",
        "Акция! Скидка {percent}%: {url}",
        "Поздравляем! Вы выиграли {amount}: {url}",
        "Кликни здесь для получения {amount}: {url}",
    ]
    
    urls = [
        "http://spam-deal.info/verify",
        "http://prize-winner.com/claim",
        "http://free-money.net/get",
        "http://lucky-draw.org/win",
        "http://bonus-gift.com/redeem",
    ]
    
    languages = ["ru", "en", "uk", "ar", "zh"]
    
    # Копируем и модифицируем сообщения
    for i in range(multiplier):
        for base_msg in base_messages:
            msg = base_msg.copy()
            
            # Генерируем новый message_id
            msg["message_id"] = f"tg_msg_{i:06d}_{base_msg['message_id']}"
            
            # Смещаем timestamp
            base_time = datetime.fromisoformat(msg["created_at"].replace("Z", "+00:00"))
            days_offset = random.randint(0, 90)
            msg["created_at"] = (base_time - timedelta(days=days_offset)).isoformat()
            
            # Модифицируем спам сообщения для разнообразия
            if msg.get("label_spam"):
                if random.random() < 0.3:  # 30% заменяем на новый паттерн
                    pattern = random.choice(spam_patterns)
                    msg["text"] = pattern.format(
                        amount=random.randint(1000, 99999),
                        percent=random.randint(10, 90),
                        url=random.choice(urls)
                    )
                    msg["language"] = random.choice(["ru", "en"])
            
            extended_messages.append(msg)
    
    # Сохраняем
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for msg in extended_messages:
            f.write(json.dumps(msg, ensure_ascii=False) + '\n')
    
    spam_count = sum(1 for m in extended_messages if m.get("label_spam"))
    ham_count = len(extended_messages) - spam_count
    
    print(f"✅ Сгенерировано {len(extended_messages):,} сообщений")
    print(f"   Spam: {spam_count:,} ({spam_count/len(extended_messages)*100:.1f}%)")
    print(f"   Ham: {ham_count:,} ({ham_count/len(extended_messages)*100:.1f}%)")
    
    return len(extended_messages), spam_count, ham_count


def simulate_stress_test_results(total_messages: int, spam_count: int) -> Dict[str, Any]:
    """
    Симулирует результаты стресс-теста на основе реалистичных оценок.
    """
    print("\n" + "="*80)
    print("СИМУЛЯЦИЯ СТРЕСС-ТЕСТА PATAS")
    print("="*80)
    
    results = {
        "dataset": {
            "total_messages": total_messages,
            "spam_count": spam_count,
            "ham_count": total_messages - spam_count,
            "spam_ratio": spam_count / total_messages,
        },
        "ingestion": {},
        "pattern_mining": {},
        "evaluation": {},
        "promotion": {},
        "costs": {},
        "quality": {},
    }
    
    # 1. Ingestion
    print("\n📥 ИНЖЕСТИЯ ДАННЫХ")
    print("-" * 80)
    
    # Реалистичная скорость: ~200 сообщений/секунду для bulk insert
    ingestion_rate = 200
    ingestion_time = total_messages / ingestion_rate
    
    results["ingestion"] = {
        "messages_per_second": ingestion_rate,
        "time_seconds": ingestion_time,
        "time_minutes": ingestion_time / 60,
        "time_hours": ingestion_time / 3600,
        "cpu_usage_percent": 20,
        "ram_usage_gb": 2.5,
    }
    
    print(f"Время загрузки: {ingestion_time/60:.1f} минут ({ingestion_time/3600:.2f} часов)")
    print(f"Скорость: {ingestion_rate} сообщений/секунду")
    
    # 2. Pattern Mining - Stage 1
    print("\n🔍 PATTERN MINING - STAGE 1 (Deterministic)")
    print("-" * 80)
    
    # Stage 1 быстрый: ~4000 сообщений/секунду
    stage1_rate = 4000
    stage1_time = total_messages / stage1_rate
    
    # Stage 1 находит ~1.5% подозрительных паттернов
    suspicious_ratio = 0.025
    suspicious_count = int(total_messages * suspicious_ratio)
    stage1_patterns = int(spam_count * 0.15)  # ~15% спам паттернов на Stage 1
    
    results["pattern_mining"]["stage1"] = {
        "time_seconds": stage1_time,
        "time_minutes": stage1_time / 60,
        "messages_processed": total_messages,
        "messages_per_second": stage1_rate,
        "patterns_found": stage1_patterns,
        "suspicious_messages": suspicious_count,
        "suspicious_ratio": suspicious_ratio,
        "cpu_usage_percent": 25,
        "ram_usage_gb": 3.0,
    }
    
    print(f"Время Stage 1: {stage1_time/60:.1f} минут")
    print(f"Найдено паттернов: {stage1_patterns:,}")
    print(f"Подозрительных для Stage 2: {suspicious_count:,} ({suspicious_ratio*100:.1f}%)")
    
    # 3. Pattern Mining - Stage 2
    print("\n🔍 PATTERN MINING - STAGE 2 (Semantic + LLM)")
    print("-" * 80)
    
    # Stage 2 медленный из-за LLM: ~0.1 сообщений/секунду (с batching)
    # Но с batching и кэшированием можно ускорить до ~1 сообщение/секунду
    stage2_rate = 1.0
    stage2_time = suspicious_count / stage2_rate
    
    # Stage 2 находит дополнительные паттерны
    stage2_patterns = int(spam_count * 0.12)  # ~12% спам паттернов на Stage 2
    total_patterns = stage1_patterns + stage2_patterns
    
    # Генерация правил: ~1.5 правила на паттерн
    rules_per_pattern = 1.5
    total_rules = int(total_patterns * rules_per_pattern)
    
    results["pattern_mining"]["stage2"] = {
        "time_seconds": stage2_time,
        "time_minutes": stage2_time / 60,
        "time_hours": stage2_time / 3600,
        "messages_processed": suspicious_count,
        "messages_per_second": stage2_rate,
        "patterns_found": stage2_patterns,
        "rules_generated": total_rules,
        "cpu_usage_percent": 40,
        "ram_usage_gb": 4.5,
    }
    
    results["pattern_mining"]["total"] = {
        "time_seconds": stage1_time + stage2_time,
        "time_minutes": (stage1_time + stage2_time) / 60,
        "time_hours": (stage1_time + stage2_time) / 3600,
        "total_patterns": total_patterns,
        "total_rules": total_rules,
    }
    
    print(f"Время Stage 2: {stage2_time/60:.1f} минут ({stage2_time/3600:.2f} часов)")
    print(f"Найдено паттернов: {stage2_patterns:,}")
    print(f"Сгенерировано правил: {total_rules:,}")
    print(f"Общее время: {(stage1_time + stage2_time)/60:.1f} минут ({(stage1_time + stage2_time)/3600:.2f} часов)")
    
    # 4. Costs
    print("\n💰 ЗАТРАТЫ НА LLM")
    print("-" * 80)
    
    # Embeddings: $0.0001 per 1K tokens
    # Среднее сообщение: ~50 tokens
    avg_tokens_per_message = 50
    embedding_cost_per_1k = 0.0001
    embedding_cost = (suspicious_count * avg_tokens_per_message / 1000) * embedding_cost_per_1k
    
    # LLM для генерации правил: ~$0.003 per rule
    llm_cost_per_rule = 0.003
    llm_cost = total_rules * llm_cost_per_rule
    
    total_cost = embedding_cost + llm_cost
    
    results["costs"] = {
        "embedding_cost_usd": embedding_cost,
        "llm_cost_usd": llm_cost,
        "total_cost_usd": total_cost,
        "cost_per_1000_messages": (total_cost / total_messages) * 1000,
        "monthly_cost_estimate_usd": total_cost * 4,  # Предполагаем еженедельный запуск
    }
    
    print(f"Embeddings: ${embedding_cost:.2f}")
    print(f"LLM генерация правил: ${llm_cost:.2f}")
    print(f"Итого за запуск: ${total_cost:.2f}")
    print(f"На 1000 сообщений: ${(total_cost / total_messages) * 1000:.4f}")
    print(f"Оценка на месяц (4 запуска): ${total_cost * 4:.2f}")
    
    # 5. Evaluation
    print("\n📊 EVALUATION")
    print("-" * 80)
    
    # Evaluation быстрое: ~15 правил/минуту
    eval_rate = 15 / 60  # правил/секунду
    eval_time = total_rules / eval_rate
    
    # Распределение правил по статусам
    candidate_ratio = 0.80
    shadow_ratio = 0.10
    active_ratio = 0.05
    deprecated_ratio = 0.05
    
    results["evaluation"] = {
        "time_seconds": eval_time,
        "time_minutes": eval_time / 60,
        "rules_evaluated": total_rules,
        "rules_per_minute": eval_rate * 60,
        "candidate_rules": int(total_rules * candidate_ratio),
        "shadow_rules": int(total_rules * shadow_ratio),
        "active_rules": int(total_rules * active_ratio),
        "deprecated_rules": int(total_rules * deprecated_ratio),
    }
    
    print(f"Время evaluation: {eval_time/60:.1f} минут")
    print(f"Оценено правил: {total_rules:,}")
    print(f"  Candidate: {int(total_rules * candidate_ratio):,}")
    print(f"  Shadow: {int(total_rules * shadow_ratio):,}")
    print(f"  Active: {int(total_rules * active_ratio):,}")
    print(f"  Deprecated: {int(total_rules * deprecated_ratio):,}")
    
    # 6. Quality Metrics
    print("\n📈 КАЧЕСТВО ПРАВИЛ")
    print("-" * 80)
    
    # Реалистичные метрики на основе архитектуры системы
    shadow_rules_count = int(total_rules * shadow_ratio)
    
    # Средняя precision для shadow правил: 0.92-0.95
    avg_precision = 0.93
    avg_recall = 0.10
    avg_f1 = 2 * (avg_precision * avg_recall) / (avg_precision + avg_recall)
    
    # С conservative profile (precision >= 0.95)
    conservative_pass_ratio = 0.25  # 25% правил проходят conservative порог
    conservative_rules = int(shadow_rules_count * conservative_pass_ratio)
    conservative_precision = 0.97
    conservative_recall = 0.08
    conservative_f1 = 2 * (conservative_precision * conservative_recall) / (conservative_precision + conservative_recall)
    
    # Coverage
    coverage_all = 0.085  # 8.5% всех спам сообщений
    coverage_conservative = 0.052  # 5.2% всех спам сообщений
    
    results["quality"] = {
        "shadow_rules": {
            "count": shadow_rules_count,
            "avg_precision": avg_precision,
            "avg_recall": avg_recall,
            "avg_f1_score": avg_f1,
            "coverage": coverage_all,
        },
        "conservative_profile": {
            "count": conservative_rules,
            "avg_precision": conservative_precision,
            "avg_recall": conservative_recall,
            "avg_f1_score": conservative_f1,
            "coverage": coverage_conservative,
        },
        "false_positive_rate": 0.0015,  # 0.15%
    }
    
    print(f"Shadow правила (precision >= 0.90):")
    print(f"  Количество: {shadow_rules_count:,}")
    print(f"  Средняя precision: {avg_precision:.3f}")
    print(f"  Средняя recall: {avg_recall:.3f}")
    print(f"  Средний F1: {avg_f1:.3f}")
    print(f"  Coverage: {coverage_all*100:.1f}%")
    
    print(f"\nConservative профиль (precision >= 0.95):")
    print(f"  Количество: {conservative_rules:,}")
    print(f"  Средняя precision: {conservative_precision:.3f}")
    print(f"  Средняя recall: {conservative_recall:.3f}")
    print(f"  Средний F1: {conservative_f1:.3f}")
    print(f"  Coverage: {coverage_conservative*100:.1f}%")
    
    print(f"\nFalse positive rate: {0.0015*100:.2f}%")
    
    # 7. Promotion
    print("\n🚀 PROMOTION")
    print("-" * 80)
    
    # С conservative profile продвигается только часть shadow правил
    promoted_count = conservative_rules
    deprecated_count = int(shadow_rules_count * 0.1)  # 10% показывают degradation
    
    results["promotion"] = {
        "promoted_to_active": promoted_count,
        "deprecated_due_to_degradation": deprecated_count,
        "final_active_rules": promoted_count,
    }
    
    print(f"Продвинуто в active: {promoted_count:,}")
    print(f"Deprecated из-за degradation: {deprecated_count:,}")
    print(f"Финальное количество active правил: {promoted_count:,}")
    
    # 8. Итоговая статистика
    print("\n" + "="*80)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("="*80)
    
    total_time = results["ingestion"]["time_seconds"] + results["pattern_mining"]["total"]["time_seconds"] + results["evaluation"]["time_seconds"]
    
    print(f"\nОбщее время обработки: {total_time/60:.1f} минут ({total_time/3600:.2f} часов)")
    print(f"  Ingestion: {results['ingestion']['time_minutes']:.1f} мин ({results['ingestion']['time_seconds']/total_time*100:.1f}%)")
    print(f"  Pattern Mining: {results['pattern_mining']['total']['time_minutes']:.1f} мин ({results['pattern_mining']['total']['time_seconds']/total_time*100:.1f}%)")
    print(f"  Evaluation: {results['evaluation']['time_minutes']:.1f} мин ({results['evaluation']['time_seconds']/total_time*100:.1f}%)")
    
    print(f"\nРесурсы:")
    print(f"  CPU: 20-40% (пики до 80% при LLM)")
    print(f"  RAM: 2.5-4.5 GB")
    print(f"  Disk I/O: умеренная")
    
    print(f"\nЗатраты:")
    print(f"  За один запуск: ${total_cost:.2f}")
    print(f"  На месяц (4 запуска): ${total_cost * 4:.2f}")
    print(f"  На 1000 сообщений: ${(total_cost / total_messages) * 1000:.4f}")
    
    print(f"\nКачество:")
    print(f"  Active правил: {promoted_count:,}")
    print(f"  Средняя precision: {conservative_precision:.3f}")
    print(f"  Средняя recall: {conservative_recall:.3f}")
    print(f"  Coverage: {coverage_conservative*100:.1f}%")
    print(f"  False positive rate: {0.0015*100:.2f}%")
    
    return results


def main():
    """Главная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Симуляция стресс-теста PATAS")
    parser.add_argument("--base-dataset", type=str, default="data/production_telegram_logs.jsonl", help="Базовый dataset")
    parser.add_argument("--output-dataset", type=str, default="data/stress_test_dataset.jsonl", help="Выходной расширенный dataset")
    parser.add_argument("--multiplier", type=int, default=10, help="Множитель для расширения dataset")
    parser.add_argument("--skip-generation", action="store_true", help="Пропустить генерацию dataset")
    parser.add_argument("--output-results", type=str, default="data/stress_test_simulation_results.json", help="Файл для сохранения результатов")
    
    args = parser.parse_args()
    
    # Генерируем dataset если нужно
    if not args.skip_generation:
        total_messages, spam_count, ham_count = generate_extended_dataset(
            args.base_dataset,
            args.output_dataset,
            args.multiplier
        )
    else:
        # Читаем существующий dataset
        total_messages = 0
        spam_count = 0
        with open(args.output_dataset, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    total_messages += 1
                    msg = json.loads(line)
                    if msg.get("label_spam"):
                        spam_count += 1
        ham_count = total_messages - spam_count
    
    # Симулируем результаты
    results = simulate_stress_test_results(total_messages, spam_count)
    
    # Сохраняем результаты
    output_path = Path(args.output_results)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n✅ Результаты сохранены в {output_path}")


if __name__ == "__main__":
    main()


