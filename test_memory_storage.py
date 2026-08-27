import asyncio
from drogue.core.storage.memory import MemoryStorage

async def test():
    s = MemoryStorage()
    await s.initialize()
    
    # Test basic operations
    await s.set('key1', 10, 60)
    val = await s.get('key1')
    assert val == 10, f'Expected 10, got {val}'
    
    # Test incr
    count = await s.incr('counter', 60, 1)
    assert count == 1
    count = await s.incr('counter', 60, 1)
    assert count == 2
    
    # Test increment_by
    count, ttl = await s.increment_by('counter2', 5, 60)
    assert count == 5
    
    # Test CAS
    ok = await s.compare_and_swap('cas_key', None, 'first', 60)
    assert ok
    ok = await s.compare_and_swap('cas_key', 'first', 'second', 60)
    assert ok
    ok = await s.compare_and_swap('cas_key', 'first', 'third', 60)
    assert not ok
    
    # Test get on non-existent
    val = await s.get('nonexistent')
    assert val is None
    
    # Test delete
    await s.delete('key1')
    val = await s.get('key1')
    assert val is None
    
    # Test exists
    await s.set('exist_key', 1, 60)
    assert await s.exists('exist_key') == True
    assert await s.exists('nonexistent') == False
    
    await s.close()
    print('MemoryStorage tests passed!')

asyncio.run(test())