import { chromium, Browser, Page } from 'playwright';
import { getRedis } from '../storage/redis';
import { isDomainAllowed } from './allowlist';
import { getLogger } from '../utils/logger';

const logger = getLogger('sandbox-executor');

interface SandboxTask {
  id: string;
  teamId: string;
  description: string;
  domains: string[];
  timeout: number;
  script?: string; // Optional Playwright script
}

let browser: Browser | null = null;

async function getBrowser(): Promise<Browser> {
  if (!browser) {
    browser = await chromium.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
    });
  }
  return browser;
}

export async function executeSandboxTask(task: SandboxTask): Promise<{ success: boolean; output: string; logs: string[] }> {
  const logs: string[] = [];
  const log = (msg: string) => {
    const entry = `[${new Date().toISOString()}] ${msg}`;
    logs.push(entry);
    logger.info(entry, { taskId: task.id });
  };

  // Verify all domains are allowed
  for (const domain of task.domains) {
    if (!await isDomainAllowed(task.teamId, domain)) {
      log(`❌ Domain not allowed: ${domain}`);
      return { success: false, output: `Domain ${domain} not in allowlist`, logs };
    }
  }

  let page: Page | null = null;
  try {
    log(`🚀 Starting task: ${task.description}`);
    const browser = await getBrowser();
    page = await browser.newPage();

    // Set timeout
    page.setDefaultTimeout(task.timeout * 1000);

    // If script provided, execute it
    if (task.script) {
      log('Executing custom script...');
      const result = await page.evaluate(task.script);
      log(`Script completed: ${JSON.stringify(result).slice(0, 500)}`);
      return { success: true, output: JSON.stringify(result), logs };
    }

    // Default: navigate to first domain and extract content
    if (task.domains.length > 0) {
      const url = task.domains[0].startsWith('http') ? task.domains[0] : `https://${task.domains[0]}`;
      log(`Navigating to ${url}`);
      await page.goto(url, { waitUntil: 'networkidle' });
      
      const title = await page.title();
      const content = await page.textContent('body');
      log(`Page title: ${title}`);
      log(`Content length: ${content?.length || 0} chars`);
      
      return { success: true, output: `Title: ${title}\n\nContent (first 3000 chars):\n${content?.slice(0, 3000)}`, logs };
    }

    log('No domains specified, nothing to do');
    return { success: true, output: 'No action taken', logs };

  } catch (error) {
    log(`❌ Error: ${error.message}`);
    return { success: false, output: error.message, logs };
  } finally {
    if (page) await page.close();
    // Store logs in Redis
    const redis = getRedis();
    await redis.lpush(`task:logs:${task.teamId}:${task.id}`, ...logs);
    await redis.expire(`task:logs:${task.teamId}:${task.id}`, 86400 * 7); // 7 days
  }
}

export async function shutdownBrowser() {
  if (browser) {
    await browser.close();
    browser = null;
  }
}
