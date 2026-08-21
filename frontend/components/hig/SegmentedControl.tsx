export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex bg-bg-tertiary rounded-hig p-1 gap-1">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`transition-hig text-subhead font-medium rounded-[9px] px-3 min-h-[32px] ${
            value === opt.value ? "bg-bg text-label shadow-sm" : "text-label-secondary"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
