import { App } from '@slack/bolt';
import { getConfig, setConfig } from '../../storage/config';
import { NIM_MODELS, FALLBACK_MODELS } from '../../../packages/shared/constants';
import { getLogger } from '../utils/logger';

const logger = getLogger('model-command');

export function registerModelCommand(app: App) {
  app.command('/model', async ({ command, ack, respond, client }) => {
    await ack();
    const args = command.text.trim().split(/\s+/);
    const subcommand = args[0]?.toLowerCase();

    try {
      const config = await getConfig(command.team_id);

      if (!subcommand || subcommand === 'status') {
        const current = config.currentModel || 'nim:meta/llama-3.1-70b-instruct';
        const provider = current.startsWith('nim:') ? 'NVIDIA NIM' : 'Fallback (Groq)';
        await respond({
          text: `*Current Model:* \`${current}\`\n*Provider:* ${provider}\n*Available NIM:* ${NIM_MODELS.join(', ')}\n*Available Fallback:* ${FALLBACK_MODELS.join(', ')}`,
          response_type: 'ephemeral'
        });
        return;
      }

      if (subcommand === 'set') {
        const modelArg = args[1];
        if (!modelArg) {
          await respond({ text: 'Usage: `/model set nim:<model-id>` or `/model set fallback:<model-id>`', response_type: 'ephemeral' });
          return;
        }

        let validatedModel: string;
        if (modelArg.startsWith('nim:')) {
          const modelId = modelArg.slice(4);
          if (!NIM_MODELS.includes(modelId as any)) {
            await respond({ text: `Unknown NIM model. Available: ${NIM_MODELS.join(', ')}`, response_type: 'ephemeral' });
            return;
          }
          validatedModel = `nim:${modelId}`;
        } else if (modelArg.startsWith('fallback:')) {
          const modelId = modelArg.slice(9);
          if (!FALLBACK_MODELS.includes(modelId as any)) {
            await respond({ text: `Unknown fallback model. Available: ${FALLBACK_MODELS.join(', ')}`, response_type: 'ephemeral' });
            return;
          }
          validatedModel = `fallback:${modelId}`;
        } else {
          await respond({ text: 'Model must start with `nim:` or `fallback:`', response_type: 'ephemeral' });
          return;
        }

        await setConfig(command.team_id, { currentModel: validatedModel });
        await respond({ text: `✅ Model updated to \`${validatedModel}\``, response_type: 'ephemeral' });
        logger.info('Model changed', { team: command.team_id, model: validatedModel, user: command.user_id });
        return;
      }

      if (subcommand === 'list') {
        await respond({
          text: `*NVIDIA NIM Models:*\n${NIM_MODELS.map(m => `• nim:${m}`).join('\n')}\n\n*Fallback Models (Groq):*\n${FALLBACK_MODELS.map(m => `• fallback:${m}`).join('\n')}`,
          response_type: 'ephemeral'
        });
        return;
      }

      await respond({ text: 'Unknown subcommand. Use: `status`, `set`, `list`', response_type: 'ephemeral' });
    } catch (error) {
      logger.error('Model command failed', { error });
      await respond({ text: '❌ Failed to process model command', response_type: 'ephemeral' });
    }
  });
}
