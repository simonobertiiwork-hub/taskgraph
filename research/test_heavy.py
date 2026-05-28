import asyncio
import time
import httpx

BASE_URL = "http://localhost:8000"

async def light_request(client: httpx.AsyncClient, i: int):
    start = time.perf_counter()
    response = await client.get(f"{BASE_URL}/tasks")
    elapsed = time.perf_counter() - start
    print(f"[Лёгкий {i}] статус {response.status_code}, время {elapsed:.3f}с")
    return elapsed

async def heavy_request(client: httpx.AsyncClient):
    start = time.perf_counter()
    response = await client.get(f"{BASE_URL}/tasks/heavy")
    elapsed = time.perf_counter() - start
    print(f"[Тяжёлый] статус {response.status_code}, время {elapsed:.3f}с")
    return elapsed

async def main():
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1 тяжёлый + 3 лёгких параллельно
        heavy_task = heavy_request(client)
        light_tasks = [light_request(client, i) for i in range(1, 4)]

        await asyncio.sleep(0.1)

        results = await asyncio.gather(
            heavy_task,
            *light_tasks,
            return_exceptions=True
        )

        for result in results:
            if isinstance(result, Exception):
                print(f"Ошибка: {type(result).__name__}")

        heavy_result = results[0]

        light_times = [
            r for r in results[1:]
            if not isinstance(r, Exception)
        ]

        if light_times:
            avg_light = sum(light_times) / len(light_times)

            print("\n--- РЕЗУЛЬТАТ ---")

        if isinstance(heavy_result, Exception):
            print("Тяжёлый запрос завершился ошибкой")
        else:
            print(f"Тяжёлый запрос: {heavy_result:.3f}с")

        if light_times:
            avg_light = sum(light_times) / len(light_times)
            print(f"Среднее время лёгких: {avg_light:.3f}с")
        else:
            print("Все лёгкие запросы завершились ошибкой")

if __name__ == "__main__":
    asyncio.run(main())