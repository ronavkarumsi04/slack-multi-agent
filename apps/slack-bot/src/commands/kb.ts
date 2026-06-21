import { App } from '@slack/bolt';
import { searchKnowledge, addKnowledge, deleteKnowledge, listKnowledge } from '../../knowledge/commands';
import { getLogger } from '../utils/logger';

const logger = getLogger('kb-command');

export function registerKBCommand(app: App) {
  app.command('/kb', async ({ command, ack, respond, client }) => {
    await ack();
    const args = command.text.trim().split(/\s+/);
    const subcommand = args[0]?.toLowerCase();
    const teamId = command.team_id;
    const userId = command.user_id;

    try {
      if (!subcommand || subcommand === 'help') {
        await respond({
          text: `*Knowledge Base Commands:*\n• \`/kb add "title" "content" #tag1 #tag2\` — Add entry\n• \`/kb search "query" [#tag]\` — Search entries\n• \`/kb list [#tag]\` — List recent entries\n• \`/kb delete <id>\` — Delete entry\n• \`/kb help\` — This help`,
          response_type: 'ephemeral'
        });
        return;
      }

      if (subcommand === 'add') {
        const text = command.text.slice(4).trim();
        const titleMatch = text.match(^"([^"]+)"$);
        if (!titleMatch) {
          await respond({ text: 'Usage: `/kb add "title" "content" #tag1 #tag2`', response_type: 'ephemeral' });
          return;
        }
        const title = titleMatch[1];
        const remaining = text.slice(titleMatch[0].length).trim();
        const contentMatch = remaining.match(^"([^"]+)"$);
        const content = contentMatch ? contentMatch[1] : remaining.split(/\s+/)[0] || '';
        const tags = [...remaining.matchAll(/#(\w+)/g)].map(m => m[1]);

        const entry = await addKnowledge(teamId, userId, title, content, tags);
        await respond({ text: `✅ Added knowledge entry \`${entry.id}\`: *${title}*`, response_type: 'ephemeral' });
        return;
      }

      if (subcommand === 'search') {
        const query = command.text.slice(7).trim();
        const tagMatch = query.match(/#(\w+)$/);
        const tag = tagMatch ? tagMatch[1] : undefined;
        const searchQuery = tag ? query.slice(0, tagMatch.index).trim() : query;

        const results = await searchKnowledge(teamId, searchQuery, tag, 5);
        if (results.length === 0) {
          await respond({ text: 'No results found.', response_type: 'ephemeral' });
          return;
        }
        const blocks = results.map(r => ({
          type: 'section',
          text: { type: 'mrkdwn', text: `*${r.title}* (${r.id})\n${r.content.slice(0, 200)}...\n_Tags: ${r.tags.join(', ') || 'none'}_` }
        }));
        await respond({ blocks, response_type: 'ephemeral' });
        return;
      }

      if (subcommand === 'list') {
        const tag = command.text.match(/#(\w+)$/)?.[1];
        const entries = await listKnowledge(teamId, tag, 10);
        if (entries.length === 0) {
          await respond({ text: 'No entries found.', response_type: 'ephemeral' });
          return;
        }
        const blocks = entries.map(e => ({
          type: 'section',
          text: { type: 'mrkdwn', text: `*${e.title}* (\`${e.id}\`)\n${e.content.slice(0, 150)}...\n_Tags: ${e.tags.join(', ') || 'none'}_` }
        }));
        await respond({ blocks, response_type: 'ephemeral' });
        return;
      }

      if (subcommand === 'delete') {
        const id = args[1];
        if (!id) {
          await respond({ text: 'Usage: `/kb delete <id>`', response_type: 'ephemeral' });
          return;
        }
        await deleteKnowledge(teamId, id);
        await respond({ text: `✅ Deleted entry \`${id}\``, response_type: 'ephemeral' });
        return;
      }

      await respond({ text: 'Unknown subcommand. Use `/kb help`', response_type: 'ephemeral' });
    } catch (error) {
      logger.error('KB command failed', { error });
      await respond({ text: '❌ Knowledge base command failed', response_type: 'ephemeral' });
    }
  });
}
