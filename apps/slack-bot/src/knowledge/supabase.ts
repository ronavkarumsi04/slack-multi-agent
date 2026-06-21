import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { getLogger } from '../utils/logger';

const logger = getLogger('supabase-kb');

let supabaseClient: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (!supabaseClient) {
    const url = process.env.SUPABASE_URL;
    const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
    if (!url || !key) {
      throw new Error('Supabase credentials not configured');
    }
    supabaseClient = createClient(url, key);
  }
  return supabaseClient;
}

export interface KBEntry {
  id: string;
  team_id: string;
  user_id: string;
  title: string;
  content: string;
  tags: string[];
  embedding?: number[];
  created_at: string;
  updated_at: string;
}

export async function addKnowledge(teamId: string, userId: string, title: string, content: string, tags: string[]): Promise<KBEntry> {
  const supabase = getSupabase();
  const id = `kb_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
  
  const { data, error } = await supabase
    .from('knowledge_base')
    .insert({
      id,
      team_id: teamId,
      user_id: userId,
      title,
      content,
      tags,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    })
    .select()
    .single();

  if (error) throw error;
  return data;
}

export async function searchKnowledge(teamId: string, query: string, tag?: string, limit = 5): Promise<KBEntry[]> {
  const supabase = getSupabase();
  
  // Simple text search (vector search would need pgvector extension)
  let queryBuilder = supabase
    .from('knowledge_base')
    .select('*')
    .eq('team_id', teamId)
    .or(`title.ilike.%${query}%,content.ilike.%${query}%`)
    .order('created_at', { ascending: false })
    .limit(limit);

  if (tag) {
    queryBuilder = queryBuilder.contains('tags', [tag]);
  }

  const { data, error } = await queryBuilder;
  if (error) throw error;
  return data || [];
}

export async function listKnowledge(teamId: string, tag?: string, limit = 10): Promise<KBEntry[]> {
  const supabase = getSupabase();
  let queryBuilder = supabase
    .from('knowledge_base')
    .select('*')
    .eq('team_id', teamId)
    .order('created_at', { ascending: false })
    .limit(limit);

  if (tag) {
    queryBuilder = queryBuilder.contains('tags', [tag]);
  }

  const { data, error } = await queryBuilder;
  if (error) throw error;
  return data || [];
}

export async function deleteKnowledge(teamId: string, id: string): Promise<void> {
  const supabase = getSupabase();
  const { error } = await supabase
    .from('knowledge_base')
    .delete()
    .eq('team_id', teamId)
    .eq('id', id);
  if (error) throw error;
}
