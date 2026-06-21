import { App, ExpressReceiver } from '@slack/bolt';
import { createSlackCommandHandlers } from './commands';
import { createSlackEventHandlers } from './events';
import { createSlackViewHandlers } from './views';
import { authMiddleware, rateLimitMiddleware } from './middleware';
import { getLogger } from '../utils/logger';

const logger = getLogger('slack-app');

export function createSlackApp() {
  const receiver = new ExpressReceiver({
    signingSecret: process.env.SLACK_SIGNING_SECRET!,
    endpoints: '/slack/events',
    processBeforeResponse: true
  });

  const app = new App({
    receiver,
    token: process.env.SLACK_BOT_TOKEN!,
    logLevel: 'info'
  });

  // Global middleware
  app.use(authMiddleware);
  app.use(rateLimitMiddleware);

  // Register handlers
  createSlackCommandHandlers(app);
  createSlackEventHandlers(app);
  createSlackViewHandlers(app);

  // Error handler
  app.error(async (error) => {
    logger.error('Slack app error', { error: error.message, stack: error.stack });
  });

  return { app, receiver };
}
