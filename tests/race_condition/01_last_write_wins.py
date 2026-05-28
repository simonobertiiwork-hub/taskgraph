import asyncio

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
    async with AsyncSessionLocal() as session:
        task = await session.scalar(
            select(Task).where(Task.id == TASK_ID)
        )
        print(
            f"{new_title}: "
            f"read_title={task.title}, "
            f"version={task.version}"
        )

        await asyncio.sleep(0.2)

        task.title= new_title

        await session.commit()

        print(
            f"{new_title}: commited"
        )


async def main():

    await reset_state()

    await asyncio.gather(
        update_task("task A"),
        update_task("task B"),
    )

    async with AsyncSessionLocal() as session:
        task = await session.scalar(
            select(Task).where(Task.id == TASK_ID)
        )

        print()
        print("FINAL STATE")

        print(
            f"title={task.title}, "
            f"version={task.version}"
        )


if __name__ == "__main__":
    asyncio.run(main())