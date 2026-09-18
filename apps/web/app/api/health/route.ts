import { NextResponse } from "next/server";

import { isLiveAnalysisEnabled } from "@/app/lib/repolume-runtime";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(
    {
      status: "ok",
      service: "repolume-web",
      live_analysis_enabled: isLiveAnalysisEnabled(),
    },
    { headers: { "cache-control": "no-store" } },
  );
}
