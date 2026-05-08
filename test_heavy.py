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
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1 тяжёлый + 5 лёгких параллельно
        heavy_task = heavy_request(client)
        light_tasks = [light_request(client, i) for i in range(1, 6)]

        results = await asyncio.gather(heavy_task, *light_tasks)

        heavy_time = results[0]
        light_times = results[1:]
        avg_light = sum(light_times) / len(light_times)

        print("\n--- РЕЗУЛЬТАТ ---")
        print(f"Тяжёлый запрос: {heavy_time:.3f}с")
        print(f"Среднее время лёгких: {avg_light:.3f}с")

if __name__ == "__main__":
    asyncio.run(main())