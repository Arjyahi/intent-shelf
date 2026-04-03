import path from "node:path";
import { readFile } from "node:fs/promises";

import { NextResponse } from "next/server";

const repoRoot = path.resolve(process.cwd(), "..");
const imageRoot = path.join(repoRoot, "data", "raw", "images");

function resolveContentType(extension) {
  switch (extension) {
    case ".jpg":
    case ".jpeg":
      return "image/jpeg";
    case ".png":
      return "image/png";
    case ".webp":
      return "image/webp";
    default:
      return "application/octet-stream";
  }
}

export async function GET(request) {
  const requestedPath = request.nextUrl.searchParams.get("path");

  if (!requestedPath) {
    return NextResponse.json(
      {
        detail: "Image path is required.",
      },
      {
        status: 400,
      },
    );
  }

  const resolvedPath = path.isAbsolute(requestedPath)
    ? requestedPath
    : path.resolve(repoRoot, requestedPath);

  if (!resolvedPath.startsWith(`${imageRoot}${path.sep}`)) {
    return NextResponse.json(
      {
        detail: "Image path is outside the approved data directory.",
      },
      {
        status: 400,
      },
    );
  }

  try {
    const fileBuffer = await readFile(resolvedPath);

    return new NextResponse(fileBuffer, {
      headers: {
        "cache-control": "public, max-age=604800, immutable",
        "content-type": resolveContentType(path.extname(resolvedPath).toLowerCase()),
      },
    });
  } catch {
    return NextResponse.json(
      {
        detail: "Image not found.",
      },
      {
        status: 404,
      },
    );
  }
}
