import { NextResponse } from "next/server";

import { fetchBackend, readJsonSafely } from "@/lib/api/backend";

export async function GET(request) {
  try {
    const query = request.nextUrl.searchParams.get("query");

    if (!query) {
      return NextResponse.json(
        {
          detail: "A search query is required.",
        },
        {
          status: 400,
        },
      );
    }

    const suffix = request.nextUrl.searchParams.toString();
    const response = await fetchBackend(`/search${suffix ? `?${suffix}` : ""}`);
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
