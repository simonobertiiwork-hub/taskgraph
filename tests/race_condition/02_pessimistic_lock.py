import asyncio
import time

from sqlalchemy import select, update

from app.db.session import AsyncSessionLocal
from app.models.task import Task


TASK_ID = 1


async def reset_state():
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Task)
            .where(Task.id == TASK_ID)
            .values(
                title="task 1",
                version=1,
            )
        )

        await session.commit()


async def update_task(new_title: str):
    started = time.perf_counter()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Task)
            .where(Task.id == TASK_ID)
            .with_for_update()
        )

        task = result.scalar_one()

        print(
            f"{new_title}: "
            f"lock acquired "
            f"(version={task.version})"
        )

        await asyncio.sleep(2)

        task.title = new_title

        await session.commit()

        elapsed = (
            time.perf_counter() - started
        )

        print(
            f"{new_title}: commited "
            f"({elapsed:.2f}s)"
        )


async def main():

    await reset_state()

    await asyncio.gather(
        update_task("task A"),
        update_task("task B"),
    )

    async with AsyncSessionLocal() as session:
        task = await session.get(
            Task,
            TASK_ID
        )

        print()
        print("FINAL STATE")

        print(
            f"title={task.title}, "
            f"version={task.version}"
        )


if __name__ == "__main__":
    asyncio.run(main())