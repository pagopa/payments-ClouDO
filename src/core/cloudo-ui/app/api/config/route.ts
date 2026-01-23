import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    googleClientId:
      process.env.GOOGLE_CLIENT_ID ||
      process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ||
      "",
  });
}
