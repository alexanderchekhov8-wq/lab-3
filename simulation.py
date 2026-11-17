"""Очереди в магазине: отдельная очередь к каждой кассе."""

import csv
from collections import deque
import json
from settings import parse_settings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def generate_day(rng, arrival_rate, service_mean, duration):
    """Приходы в течение рабочего дня; времена измеряются в минутах."""
    arrivals = []
    time = 0.0
    while True:
        time += rng.exponential(60 / arrival_rate)
        if time >= duration:
            break
        arrivals.append(time)
    return np.array(arrivals), rng.exponential(service_mean, len(arrivals))


def serve(arrivals, services, cashiers, duration, threshold, rng):
    """Выбор самой короткой очереди с учётом обслуживаемого покупателя.

    Равные по длине очереди выбираются случайно. Переходов между ними нет.
    В каждой очереди покупатели обслуживаются в порядке прихода.
    После закрытия новые покупатели не приходят, оставшихся обслуживаем.
    Загрузка учитывает только пересечение обслуживания с рабочим днём.
    """
    # В очередях хранятся времена завершения обслуживания всех ещё не ушедших.
    queues = [deque() for _ in range(cashiers)]
    available = [0.0] * cashiers
    waits = []
    busy = 0.0
    for arrival, service in zip(arrivals, services):
        for queue in queues:
            while queue and queue[0] <= arrival:
                queue.popleft()
        shortest = min(map(len, queues))
        candidates = [i for i, queue in enumerate(queues) if len(queue) == shortest]
        cashier = candidates[0] if len(candidates) == 1 else int(rng.choice(candidates))
        start = max(arrival, available[cashier])
        end = start + service
        queues[cashier].append(end)
        available[cashier] = end
        waits.append(start - arrival)
        busy += max(0.0, min(end, duration) - start)
    waits = np.array(waits)
    return {
        "customers": len(waits),
        "mean_wait_min": float(waits.mean()) if len(waits) else 0.0,
        "share_over_threshold": float((waits > threshold).mean()) if len(waits) else 0.0,
        "utilization": busy / (cashiers * duration),
        "overtime_min": max(0.0, max(available) - duration),
    }, waits


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    args = parse_settings()
    print(f"Поток: {args.arrival_rate:g} чел/ч; обслуживание: {args.service_mean:g} мин; "
          f"рабочий день: {args.hours:g} ч; кассы: {args.cashiers}; дней: {args.runs}")
    print("У каждой кассы своя очередь; выбор самой короткой, без переходов.")

    rng = np.random.default_rng(args.seed)
    duration = args.hours * 60
    records = []
    counts = args.cashiers
    for run in range(1, args.runs + 1):
        arrivals, services = generate_day(rng, args.arrival_rate, args.service_mean, duration)
        # Общие входные данные позволяют сравнить кассы при одинаковом спросе.
        for cashiers in counts:
            # Выбор очереди не меняет входной поток и не зависит от набора вариантов.
            routing_rng = np.random.default_rng(np.random.SeedSequence([args.seed, run, cashiers, 1]))
            metrics, _ = serve(arrivals, services, cashiers, duration, args.threshold, routing_rng)
            records.append({"run": run, "cashiers": cashiers, **metrics})

    summary = []
    for cashiers in counts:
        days = [row for row in records if row["cashiers"] == cashiers]
        daily_means = np.array([row["mean_wait_min"] for row in days])
        half_width = 1.96 * daily_means.std(ddof=1) / np.sqrt(args.runs)
        mean = float(daily_means.mean())
        summary.append({
            "cashiers": cashiers,
            "mean_wait_min": mean,
            "ci95_low_min": mean - half_width,
            "ci95_high_min": mean + half_width,
            "share_over_threshold": float(np.mean([d["share_over_threshold"] for d in days])),
            "utilization": float(np.mean([d["utilization"] for d in days])),
            "mean_customers_per_day": float(np.mean([d["customers"] for d in days])),
            "mean_overtime_min": float(np.mean([d["overtime_min"] for d in days])),
        })

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "daily_results.csv", records)
    write_csv(args.output / "summary.csv", summary)
    config = {key: str(value) if key == "output" else value for key, value in vars(args).items()}
    (args.output / "parameters.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    counts = [row["cashiers"] for row in summary]
    means = [row["mean_wait_min"] for row in summary]
    errors = [row["ci95_high_min"] - row["mean_wait_min"] for row in summary]
    axes[0].bar(counts, means, yerr=errors, capsize=5, color="#377eb8")
    axes[0].axhline(args.threshold, color="#d95f02", linestyle="--", label=f"Порог {args.threshold:g} мин")
    axes[0].set_ylabel("Среднее ожидание, мин")
    axes[0].set_title("Ожидание и 95% интервал")
    axes[0].legend()
    axes[1].bar(counts, [100 * row["share_over_threshold"] for row in summary], color="#377eb8")
    axes[1].set_ylabel("Доля покупателей, %")
    axes[1].set_title(f"Ожидание больше {args.threshold:g} минут")
    axes[2].bar(counts, [100 * row["utilization"] for row in summary], color="#377eb8")
    axes[2].set_ylabel("Загрузка, %")
    axes[2].set_ylim(0, 100)
    axes[2].set_title("Загрузка касс в рабочие часы")
    for ax in axes:
        ax.set_xticks(counts)
        ax.set_xlabel("Число касс")
        ax.grid(axis="y", alpha=0.25)
        ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(args.output / "comparison.png", dpi=180)
    plt.close(fig)

    print("Кассы | Ожидание, мин | 95% интервал | Доля > порога | Загрузка")
    for row in summary:
        print(f"{row['cashiers']:5} | {row['mean_wait_min']:13.3f} | "
              f"[{row['ci95_low_min']:.3f}; {row['ci95_high_min']:.3f}] | "
              f"{row['share_over_threshold']:13.1%} | {row['utilization']:.1%}")
    print(f"Результаты сохранены: {args.output}")


if __name__ == "__main__":
    main()
