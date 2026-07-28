import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export function GET(): NextResponse {
  return NextResponse.json({ status: "ok", service: "sip-web", version: "1.1.0" }, { headers: { "Cache-Control": "no-store" } });
}
