import { NextResponse } from "next/server";

import { fetchBackend, readJsonSafely } from "@/lib/api/backend";

export async function PUT(request, { params }) {
  try {
    const { productId } = await params;
    const body = await request.json();
    const response = await fetchBackend(`/cart/items/${productId}`, {
      method: "PUT",
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

export async function DELETE(request, { params }) {
  try {
    const { productId } = await params;
    const suffix = request.nextUrl.searchParams.toString();
    const response = await fetchBackend(
      `/cart/items/${productId}${suffix ? `?${suffix}` : ""}`,
      {
        method: "DELETE",
      },
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
