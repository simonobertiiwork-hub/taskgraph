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
            select(Task)
            .where(Task.id == TASK_ID)
        )

        current_version = task.version

        print(
            f"{new_title}: "
            f"read version={current_version}"
        )

        await asyncio.sleep(0.2)

        result = await session.execute(
            update(Task)
            .where(
                Task.id == TASK_ID,
                Task.version == current_version
            )
            .values(
                title=new_title,
                version=current_version + 1
            )
        )

        if result.rowcount == 0:

            await session.rollback()

            print(
                f"{new_title}: conflict detected"
            )

            return

        await session.commit()

        print(
            f"{new_title}: committed "
            f"version={current_version + 1}"
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
            f"title={task.title}"
        )

        print(
            f"version={task.version}"
        )


if __name__ == "__main__":
    asyncio.run(main())