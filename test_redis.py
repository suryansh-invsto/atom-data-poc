import redis.asyncio as redis
import asyncio

async def test():
    r = await redis.from_url('redis://localhost:6379')
    result = await r.ping()
    print(f'PING: {result}')
    await r.set('test', 'hello')
    value = await r.get('test')
    print(f'GET: {value}')
    await r.aclose()
    print('SUCCESS')

asyncio.run(test())
