"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Federation is now a tab on the National workspace (/national), not a separate destination —
 * this redirect keeps any existing link to this path working. */
export default function Page() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/national");
  }, [router]);
  return null;
}
