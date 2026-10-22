import { useEffect, useState } from "react";
import { toast } from "sonner";
import { adminApi, fmtErr } from "./api";

export default function EnquiriesTab() {
  const [list, setList] = useState(null);

  useEffect(() => {
    adminApi.get("/admin/enquiries").then((r) => setList(r.data)).catch((e) => { toast.error(fmtErr(e)); setList([]); });
  }, []);

  if (list === null) return <p className="font-mono text-xs text-slate-500">loading…</p>;
  if (list.length === 0) return <p className="font-mono text-xs text-slate-500" data-testid="enquiries-empty">Abhi tak koi enquiry nahi aayi.</p>;

  return (
    <div className="grid gap-3" data-testid="enquiries-tab">
      {list.map((q) => (
        <div key={q.id} className="rounded-xl border border-white/10 bg-panel p-5">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-bold text-slate-100">{q.name} <span className="ml-2 font-mono text-[11px] font-normal text-emerald-400">{q.email}</span></p>
            <p className="font-mono text-[11px] text-slate-500">{new Date(q.created_at).toLocaleString()}</p>
          </div>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-400">{q.message}</p>
        </div>
      ))}
    </div>
  );
}
