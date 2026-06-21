import { Redis } from '@upstash/redis';
import { getLogger } from '../utils/logger';

const logger = getLogger('redis');

let redisClient: Redis | null = null;

export function getRedis(): Redis {
  if (!redisClient) {
    const url = process.env.UPSTASH_REDIS_REST_URL;
    const token = process.env.UPSTASH_REDIS_REST_TOKEN;
    if (!url || !token) {
      throw new Error('Upstash Redis credentials not configured');
    }
    redisClient = new Redis({ url, token });
  }
  return redisClient;
}

export async function getSession(teamId: string, channelId: string) {
  const redis = getRedis();
  const key = `session:${teamId}:${channelId}`;
  const data = await redis.get(key);
  return data || { messages: [], createdAt: Date.now() };
}

export async function updateSession(teamId: string, channelId: string, session: any) {
  const redis = getRedis();
  const key = `session:${teamId}:${channelId}`;
  await redis.set(key, JSON.stringify(session), { ex: 86400 * 30 }); // 30 days
}

export async function getConfig(teamId: string) {
  const redis = getRedis();
  const key = `config:${teamId}`;
  const data = await redis.get(key);
  return data || { currentModel: 'nim:meta/llama-3.1-70b-instruct' };
}

export async function setConfig(teamId: string, config: any) {
  const redis = getRedis();
  const key = `config:${teamId}`;
  const current = await getConfig(teamId);
  await redis.set(key, JSON.stringify({ ...current, ...config }));
}

export async function getTaskLogs(teamId: string, taskId: string): Promise<string[]> {
  const redis = getRedis();
  const key = `task:logs:${teamId}:${taskId}`;
  const logs = await redis.lrange(key, 0, -1);
  return logs.reverse();
}
