import asyncio
import time

import httpx


async def make_request(client: httpx.AsyncClient, i: int):
    """Отправляет запрос к /tasks/slow и выводит время выполнения."""
    start = time.perf_counter()
    response = await client.get("http://localhost:8000/tasks/slow")
    elapsed = time.perf_counter() - start
    print(f"Запрос {i}: статус {response.status_code}, время {elapsed:.2f}с")


async def main():
    """Запускает 7 параллельных запросов, чтобы показать pool exhaustion."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 7 запросов → 5 сразу, 2 в очереди
        tasks = [make_request(client, i) for i in range(1, 12)]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())