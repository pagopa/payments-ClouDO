import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  return handleRequest(request);
}

export async function POST(request: NextRequest) {
  return handleRequest(request);
}

export async function PUT(request: NextRequest) {
  return handleRequest(request);
}

export async function DELETE(request: NextRequest) {
  return handleRequest(request);
}

export async function PATCH(request: NextRequest) {
  return handleRequest(request);
}

async function handleRequest(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const path = searchParams.get("path");

  if (!path) {
    return NextResponse.json(
      { error: "Missing path parameter" },
      { status: 400 },
    );
  }

  const apiUrl = process.env.API_URL || "http://localhost:7071/api";
  const cloudoKey = process.env.CLOUDO_KEY || "";
  const functionKey = process.env.FUNCTION_KEY || "";

  let cleanPath = path;
  const apiPrefix = "/api";
  if (apiUrl.endsWith(apiPrefix) && path.startsWith(apiPrefix)) {
    cleanPath = path.substring(apiPrefix.length);
  }

  const targetUrl = new URL(
    `${apiUrl}${cleanPath.startsWith("/") ? "" : "/"}${cleanPath}`,
  );

  // Only append search params that are not already in the path
  searchParams.forEach((value, key) => {
    if (key !== "path" && !targetUrl.searchParams.has(key)) {
      targetUrl.searchParams.append(key, value);
    }
  });

  const headers = new Headers();
  const headersToForward = ["content-type", "authorization"];
  headersToForward.forEach((header) => {
    const value = request.headers.get(header);
    if (value) {
      headers.set(header, value);
    }
  });

  headers.set("x-cloudo-key", cloudoKey);
  headers.set("x-functions-key", functionKey);

  // Forward user information from the session if available in the Authorization header
  const authHeader = request.headers.get("authorization");
  if (authHeader && authHeader.startsWith("Bearer ")) {
    try {
      const token = authHeader.split(" ")[1];
      const parts = token.split(".");
      // Our internal tokens are 2 parts (payload.sig), standard JWTs are 3 parts (header.payload.sig)
      const payloadB64 = parts.length === 2 ? parts[0] : parts[1];

      if (payloadB64) {
        const payload = JSON.parse(
          Buffer.from(
            payloadB64.replace(/-/g, "+").replace(/_/g, "/"),
            "base64",
          ).toString(),
        );
        if (payload.username || payload.email) {
          headers.set("x-cloudo-user", payload.username || payload.email);
        }
      }
    } catch (e) {
      console.warn("Could not extract user from token:", e);
    }
  }

  try {
    const body = ["POST", "PUT", "PATCH", "DELETE"].includes(request.method)
      ? await request.text()
      : undefined;

    const response = await fetch(targetUrl.toString(), {
      method: request.method,
      headers,
      body: body || undefined,
    });

    const contentType = response.headers.get("content-type");
    let data;
    if (contentType && contentType.includes("application/json")) {
      const text = await response.text();
      data = text ? JSON.parse(text) : {};
    } else {
      data = { message: await response.text() };
    }

    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Unknown error";
    console.error(`Proxy error connecting to ${targetUrl.toString()}:`, error);
    return NextResponse.json(
      {
        error: "Proxy request failed",
        details: errorMessage,
        target: targetUrl.toString(),
      },
      { status: 500 },
    );
  }
}
