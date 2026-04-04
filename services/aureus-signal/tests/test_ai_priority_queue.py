import asyncio
import time
import unittest

# Priority Constants
PRIO_TRADE = 1
PRIO_PULSE = 2


class TestAIPriorityQueue(unittest.IsolatedAsyncioTestCase):
    async def test_priority_queue(self):
        print("🧪 Starting AI Priority Queue Test...")
        queue = asyncio.PriorityQueue()
        results = []
        count = 0

        async def mock_worker(worker_id):
            while True:
                item = await queue.get()
                # Sentinel: task_type is None
                if item[2] is None: 
                    queue.task_done()
                    break
                    
                priority, _, task_type, payload = item
                print(f"  [Worker {worker_id}] Processing {task_type} (Prio: {priority}) for {payload['symbol']}")
                
                # Simulate LLM Latency
                await asyncio.sleep(0.5) 
                
                results.append((priority, task_type, payload['symbol']))
                queue.task_done()

        # 1. Test Priority Jump
        print("Phase 1: Testing Priority Jump...")
        results.clear()
        # Add 3 Pulse requests
        for i in range(3):
            count += 1
            await queue.put((PRIO_PULSE, count, 'PULSE', {'symbol': f'PULSE_{i}'}))
        
        # Add 1 Audit request
        count += 1
        await queue.put((PRIO_TRADE, count, 'AUDIT', {'symbol': 'TRADE_URGENT'}))
        
        # Sentinel to stop worker (tuple to avoid comparison errors)
        await queue.put((99, 999, None, None))
        
        worker = asyncio.create_task(mock_worker(0))
        await asyncio.gather(worker)
        
        print(f"Capture Results: {[r[2] for r in results]}")
        self.assertEqual(results[0][1], 'AUDIT', "High priority AUDIT should be processed first")
        print("✅ Priority Jump verified.")

        # 2. Test Parallelism
        print("\nPhase 2: Testing Parallelism...")
        results.clear()
        for i in range(4):
            count += 1
            await queue.put((PRIO_PULSE, count, 'PULSE', {'symbol': f'Parallel_{i}'}))
        
        # Sentinels for 2 workers
        await queue.put((99, 1000, None, None))
        await queue.put((99, 1001, None, None))
        
        start_time = time.time()
        workers = [asyncio.create_task(mock_worker(i)) for i in range(2)]
        await asyncio.gather(*workers)
        duration = time.time() - start_time
        
        print(f"Processed 4 tasks with 2 workers in {duration:.2f}s")
        self.assertLess(duration, 1.5, f"Parallel processing failed, took {duration:.2f}s")
        print("✅ Parallelism verified (2 workers).")

        print("\n🎉 All Step 2 Priority Queue tests passed!")

if __name__ == "__main__":
    unittest.main()
