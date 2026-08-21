"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Hospital management is now the "Hospital" tab on /shc, not a separate destination — this
 * redirect keeps any existing link to this path working. */
export default function Page() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/shc");
  }, [router]);
  return null;
}
