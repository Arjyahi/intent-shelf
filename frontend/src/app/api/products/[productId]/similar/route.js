import { NextResponse } from "next/server";

import { fetchBackend, readJsonSafely } from "@/lib/api/backend";

export async function GET(request, { params }) {
  try {
    const { productId } = await params;
    const k = request.nextUrl.searchParams.get("k");
    const suffix = k ? `?k=${encodeURIComponent(k)}` : "";

    const response = await fetchBackend(`/products/${productId}/similar${suffix}`);
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
