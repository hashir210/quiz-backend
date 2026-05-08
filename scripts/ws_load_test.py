import argparse
import asyncio
import json
import random
import string
import time

import websockets


def _rand_name(i: int) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"student{i:02d}_{suffix}"


async def _student(uri: str, name: str, results: dict, answer_after_s: float | None):
    t0 = time.perf_counter()
    try:
        async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as ws:
            await ws.send(json.dumps({"event": "join", "name": name, "role": "student"}))
            results["connected"] += 1

            async def reader():
                async for msg in ws:
                    try:
                        data = json.loads(msg)
                    except Exception:
                        continue
                    # Track a couple of event types to confirm broadcast works.
                    evt = data.get("event")
                    if evt:
                        results["events"][evt] = results["events"].get(evt, 0) + 1

            read_task = asyncio.create_task(reader())

            if answer_after_s is not None:
                await asyncio.sleep(answer_after_s)
                # This only has an effect if a real quiz session is active.
                await ws.send(json.dumps({"event": "student_answer", "option": random.randint(0, 3)}))

            await asyncio.sleep(2)
            read_task.cancel()
            with contextlib.suppress(Exception):
                await read_task
    except Exception:
        results["failed"] += 1
    finally:
        results["latencies_ms"].append((time.perf_counter() - t0) * 1000)


async def _teacher(uri: str, name: str, results: dict):
    try:
        async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as ws:
            await ws.send(json.dumps({"event": "join", "name": name, "role": "teacher"}))
            await asyncio.sleep(0.5)
            # Will only start if a DB session exists for this room_code.
            await ws.send(json.dumps({"event": "teacher_start"}))
            await asyncio.sleep(1.0)
    except Exception:
        results["teacher_failed"] += 1


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--room", default="TEST01")
    parser.add_argument("--students", type=int, default=30)
    parser.add_argument("--answers", action="store_true")
    args = parser.parse_args()

    uri = f"ws://{args.host}:{args.port}/ws/{args.room}"

    results = {
        "connected": 0,
        "failed": 0,
        "teacher_failed": 0,
        "events": {},
        "latencies_ms": [],
    }

    teacher_task = asyncio.create_task(_teacher(uri, "Teacher", results))

    # Stagger connections slightly to mimic a real join burst.
    tasks = []
    for i in range(args.students):
        await asyncio.sleep(0.02)
        answer_after = (0.5 + random.random()) if args.answers else None
        tasks.append(asyncio.create_task(_student(uri, _rand_name(i), results, answer_after)))

    await asyncio.gather(*tasks, return_exceptions=True)
    await teacher_task

    lat = results["latencies_ms"]
    lat.sort()
    p50 = lat[int(0.50 * (len(lat) - 1))] if lat else 0
    p90 = lat[int(0.90 * (len(lat) - 1))] if lat else 0
    p99 = lat[int(0.99 * (len(lat) - 1))] if lat else 0

    print("WS load test results")
    print(f"- uri: {uri}")
    print(f"- students: {args.students}")
    print(f"- connected: {results['connected']}")
    print(f"- failed: {results['failed']}")
    print(f"- teacher_failed: {results['teacher_failed']}")
    print(f"- client_lifetime_latency_ms: p50={p50:.1f} p90={p90:.1f} p99={p99:.1f}")
    print(f"- events_seen: {json.dumps(results['events'], indent=2, sort_keys=True)}")


if __name__ == "__main__":
    import contextlib

    asyncio.run(main())

