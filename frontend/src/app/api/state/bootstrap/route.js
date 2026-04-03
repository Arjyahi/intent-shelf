import { NextResponse } from "next/server";

import { fetchBackend, readJsonSafely } from "@/lib/api/backend";

export async function GET(request) {
  try {
    const suffix = request.nextUrl.searchParams.toString();
    const response = await fetchBackend(
      `/state/bootstrap${suffix ? `?${suffix}` : ""}`,
    );
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
