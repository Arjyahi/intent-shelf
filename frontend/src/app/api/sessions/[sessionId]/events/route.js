import { NextResponse } from "next/server";

import { fetchBackend, readJsonSafely } from "@/lib/api/backend";

export async function POST(request, { params }) {
  try {
    const { sessionId } = await params;
    const body = await request.json();
    const response = await fetchBackend(`/sessions/${sessionId}/events`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    const payload = await readJsonSafely(response);

    return NextResponse.json(payload || {}, {
      status: response.status,
    });
  } catch (error) {
    return NextResponse.json(
      {
        detail: error.message || "We couldn't connect right now.",
      },
      {
        status: 500,
      },
    );
  }
}
