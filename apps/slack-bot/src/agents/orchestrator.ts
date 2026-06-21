import { App } from '@slack/bolt';
import { AGENTS, CHANNELS } from '../../../packages/shared/constants';
import { getPrompt } from '../../../packages/shared/prompts';
import { getLLMResponse } from '../../llm/router';
import { searchKnowledge, addKnowledge } from '../../knowledge/commands';
import { getSession, updateSession } from '../../storage/session';
import { getLogger } from '../utils/logger';

const logger = getLogger('orchestrator');

export class AureliusOrchestrator {
  private app: App;
  private teamId: string;

  constructor(app: App, teamId: string) {
    this.app = app;
    this.teamId = teamId;
  }

  async handleMention(message: any) {
    const userText = message.text.replace(/<@[A-Z0-9]+>/, '').trim();
    const session = await getSession(this.teamId, message.channel);

    // Add user message to session
    session.messages.push({ role: 'user', content: userText, user: message.user });
    await updateSession(this.teamId, message.channel, session);

    // Search knowledge base for context
    const kbResults = await searchKnowledge(this.teamId, userText, undefined, 3);
    const kbContext = kbResults.length > 0
      ? '\n\n*Relevant Knowledge:*\n' + kbResults.map(r => `- ${r.title}: ${r.content.slice(0, 300)}`).join('\n')
      : '';

    // Build system prompt with context
    const systemPrompt = getPrompt(AGENTS.AURELIUS) + kbContext;

    // Get Aurelius response
    const response = await getLLMResponse(this.teamId, [
      { role: 'system', content: systemPrompt },
      ...session.messages.slice(-10)
    ]);

    // Parse response for agent delegation
    const delegations = this.parseDelegations(response);

    // Post Aurelius response
    await this.app.client.chat.postMessage({
      channel: message.channel,
      text: response,
      thread_ts: message.ts
    });

    // Execute delegations
    for (const delegation of delegations) {
      await this.delegateToAgent(delegation.agent, delegation.task, message.channel, message.ts);
    }

    // Update session
    session.messages.push({ role: 'assistant', content: response });
    await updateSession(this.teamId, message.channel, session);
  }

  private parseDelegations(response: string): Array<{ agent: string; task: string }> {
    const delegations: Array<{ agent: string; task: string }> = [];
    const lines = response.split('\n');
    let currentAgent = '';
    let currentTask = '';

    for (const line of lines) {
      const agentMatch = line.match(/^@?(Maya|Ethan|Lena|Iris|Omar|Kai|Noah)[:,]\s*(.+)$/i);
      if (agentMatch) {
        if (currentAgent && currentTask) {
          delegations.push({ agent: currentAgent, task: currentTask.trim() });
        }
        currentAgent = agentMatch[1];
        currentTask = agentMatch[2];
      } else if (currentAgent && line.trim()) {
        currentTask += ' ' + line.trim();
      }
    }
    if (currentAgent && currentTask) {
      delegations.push({ agent: currentAgent, task: currentTask.trim() });
    }
    return delegations;
  }

  private async delegateToAgent(agentName: string, task: string, channel: string, threadTs: string) {
    const agentChannel = CHANNELS[agentName.toUpperCase() as keyof typeof CHANNELS] || CHANNELS.GENERAL;
    
    await this.app.client.chat.postMessage({
      channel: agentChannel,
      text: `*Delegation from Aurelius:*\n${task}`,
      thread_ts: threadTs
    });

    // Trigger specialist agent
    const specialist = this.getSpecialist(agentName);
    if (specialist) {
      specialist.handleTask(task, agentChannel, threadTs);
    }
  }

  private getSpecialist(agentName: string) {
    // Import dynamically to avoid circular deps
    const specialists: Record<string, any> = {
      Maya: require('./maya').MayaSpecialist,
      Ethan: require('./ethan').EthanSpecialist,
      Lena: require('./lena').LenaSpecialist,
      Iris: require('./iris').IrisSpecialist,
      Omar: require('./omar').OmarSpecialist,
      Kai: require('./kai').KaiSpecialist,
      Noah: require('./noah').NoahSpecialist
    };
    return specialists[agentName];
  }

  async summarizeDiscussion(channel: string, threadTs: string) {
    const result = await this.app.client.conversations.replies({
      channel,
      ts: threadTs,
      limit: 50
    });

    const messages = result.messages?.filter(m => m.subtype !== 'bot_message') || [];
    const conversation = messages.map(m => `<@${m.user}>: ${m.text}`).join('\n');

    const summaryPrompt = `Summarize this agent discussion in 3-5 bullet points. Identify: 1) Key decisions, 2) Open questions, 3) Conflicts, 4) Next steps. Be concise.`;
    const summary = await getLLMResponse(this.teamId, [
      { role: 'system', content: summaryPrompt },
      { role: 'user', content: conversation }
    ]);

    // Post summary and request confirmation
    await this.app.client.chat.postMessage({
      channel: CHANNELS.APPROVALS,
      blocks: [
        { type: 'header', text: { type: 'plain_text', text: '📋 Discussion Summary — Awaiting Confirmation' } },
        { type: 'section', text: { type: 'mrkdwn', text: `*Channel:* <#${channel}> | *Thread:* ${threadTs}` } },
        { type: 'section', text: { type: 'mrkdwn', text: summary } },
        { type: 'actions', elements: [
          { type: 'button', text: { type: 'plain_text', text: '✅ Approve & Execute' }, action_id: `approve_summary_${channel}_${threadTs}`, style: 'primary', value: JSON.stringify({ channel, threadTs, summary }) },
          { type: 'button', text: { type: 'plain_text', text: '❌ Reject' }, action_id: `reject_summary_${channel}_${threadTs}`, style: 'danger', value: JSON.stringify({ channel, threadTs }) },
          { type: 'button', text: { type: 'plain_text', text: '🔄 Request Changes' }, action_id: `revise_summary_${channel}_${threadTs}`, value: JSON.stringify({ channel, threadTs }) }
        ]}
      ]
    });
  }
}
