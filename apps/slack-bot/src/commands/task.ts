import { App } from '@slack/bolt';
import { requestApproval, getPendingApprovals, approveTask, rejectTask } from '../../sandbox/approvals';
import { executeSandboxTask } from '../../sandbox/executor';
import { getLogger } from '../utils/logger';

const logger = getLogger('task-command');

export function registerTaskCommand(app: App) {
  app.command('/task', async ({ command, ack, respond, client }) => {
    await ack();
    const args = command.text.trim().split(/\s+/);
    const subcommand = args[0]?.toLowerCase();
    const teamId = command.team_id;
    const userId = command.user_id;

    try {
      if (!subcommand || subcommand === 'help') {
        await respond({
          text: `*Kai Automation Commands:*\n• \`/task run "description" --domains example.com,api.github.com --timeout 60\` — Request automation\n• \`/task approve <task-id>\` — Approve pending task\n• \`/task reject <task-id> "reason"\` — Reject pending task\n• \`/task list\` — List pending/running tasks\n• \`/task logs <task-id>\` — View task logs\n• \`/task allowlist add|remove <domain>\` — Manage allowed domains`,
          response_type: 'ephemeral'
        });
        return;
      }

      if (subcommand === 'run') {
        const text = command.text.slice(4).trim();
        const descMatch = text.match(^"([^"]+)"$);
        if (!descMatch) {
          await respond({ text: 'Usage: `/task run "description" --domains example.com --timeout 60`', response_type: 'ephemeral' });
          return;
        }
        const description = descMatch[1];
        const domainMatch = text.match(/--domains\s+([^\s]+)/);
        const domains = domainMatch ? domainMatch[1].split(',').map(d => d.trim()) : [];
        const timeoutMatch = text.match(/--timeout\s+(\d+)/);
        const timeout = timeoutMatch ? parseInt(timeoutMatch[1], 10) : 60;

        const approval = await requestApproval(teamId, userId, description, domains, timeout);
        await respond({
          text: `🤖 *Task submitted for approval*\n*ID:* \`${approval.id}\`\n*Description:* ${description}\n*Domains:* ${domains.join(', ') || 'none (will be rejected)'}\n*Timeout:* ${timeout}s\n\nKai will post in <#${process.env.SLACK_APPROVALS_CHANNEL}> for approval.`,
          response_type: 'ephemeral'
        });
        return;
      }

      if (subcommand === 'approve') {
        const taskId = args[1];
        if (!taskId) {
          await respond({ text: 'Usage: `/task approve <task-id>`', response_type: 'ephemeral' });
          return;
        }
        await approveTask(teamId, taskId, userId);
        await respond({ text: `✅ Task \`${taskId}\` approved. Kai will execute shortly.`, response_type: 'ephemeral' });
        return;
      }

      if (subcommand === 'reject') {
        const taskId = args[1];
        const reason = args.slice(2).join(' ') || 'No reason provided';
        if (!taskId) {
          await respond({ text: 'Usage: `/task reject <task-id> "reason"`', response_type: 'ephemeral' });
          return;
        }
        await rejectTask(teamId, taskId, userId, reason);
        await respond({ text: `❌ Task \`${taskId}\` rejected: ${reason}`, response_type: 'ephemeral' });
        return;
      }

      if (subcommand === 'list') {
        const pending = await getPendingApprovals(teamId);
        if (pending.length === 0) {
          await respond({ text: 'No pending tasks.', response_type: 'ephemeral' });
          return;
        }
        const blocks = pending.map(p => ({
          type: 'section',
          text: { type: 'mrkdwn', text: `*\`${p.id}\`* — ${p.description}\n_Domains: ${p.domains.join(', ') || 'none'} | Requested by <@${p.requestedBy}>_` },
          accessory: {
            type: 'button',
            text: { type: 'plain_text', text: 'Approve' },
            action_id: `approve_${p.id}`,
            value: p.id
          }
        }));
        await respond({ blocks, response_type: 'ephemeral' });
        return;
      }

      if (subcommand === 'logs') {
        const taskId = args[1];
        if (!taskId) {
          await respond({ text: 'Usage: `/task logs <task-id>`', response_type: 'ephemeral' });
          return;
        }
        // Fetch logs from Redis
        const { getTaskLogs } = await import('../../storage/redis');
        const logs = await getTaskLogs(teamId, taskId);
        await respond({ text: logs.length ? logs.join('\n') : 'No logs yet.', response_type: 'ephemeral' });
        return;
      }

      if (subcommand === 'allowlist') {
        const action = args[1];
        const domain = args[2];
        if (!action || !domain || !['add', 'remove'].includes(action)) {
          await respond({ text: 'Usage: `/task allowlist add|remove <domain>`', response_type: 'ephemeral' });
          return;
        }
        const { updateAllowlist } = await import('../../sandbox/allowlist');
        await updateAllowlist(teamId, domain, action === 'add');
        await respond({ text: `${action === 'add' ? '✅ Added' : '🗑️ Removed'} \`${domain}\` from allowlist.`, response_type: 'ephemeral' });
        return;
      }

      await respond({ text: 'Unknown subcommand. Use `/task help`', response_type: 'ephemeral' });
    } catch (error) {
      logger.error('Task command failed', { error });
      await respond({ text: '❌ Task command failed', response_type: 'ephemeral' });
    }
  });

  // Button actions for approvals
  app.action(/approve_(.+)/, async ({ ack, body, respond }) => {
    await ack();
    const taskId = body.actions[0].value;
    const userId = body.user.id;
    const teamId = body.team.id;
    await approveTask(teamId, taskId, userId);
    await respond({ text: `✅ You approved task \`${taskId}\``, response_type: 'ephemeral' });
  });
}
