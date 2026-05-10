/**
 * Conversations Endpoint - Create new chat session
 */

import { NextResponse } from 'next/server';
import { vaquillClient } from '@/lib/ai/vaquill-client';

export async function POST() {
  try {
    const conversation = await vaquillClient.createConversation();

    return NextResponse.json({
      success: true,
      session_id: conversation.session_id,
      data: conversation,
    });
  } catch (error: any) {
    console.error('[API] Create conversation error:', error);
    return NextResponse.json(
      { success: false, error: error.message },
      { status: 500 }
    );
  }
}
