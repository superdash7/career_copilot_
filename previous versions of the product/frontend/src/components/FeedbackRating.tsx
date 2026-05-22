import { useState } from 'react';
import { ThumbsUp, ThumbsDown, Check } from 'lucide-react';

export default function FeedbackRating() {
  const [submitted, setSubmitted] = useState(false);
  const [rating, setRating] = useState<'up' | 'down' | null>(null);

  const submit = (value: 'up' | 'down') => {
    setRating(value);
    setSubmitted(true);
  };

  if (submitted) {
    return (
      <div className="fade-in flex items-center gap-2 text-sm text-(--color-text-muted)">
        <Check className="h-4 w-4 text-emerald-500" />
        <span>Спасибо за обратную связь!</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-(--color-text-muted)">Насколько полезен план?</span>
      <div className="flex gap-1">
        <button
          onClick={() => submit('up')}
          className={`p-2 rounded-lg transition-all ${
            rating === 'up'
              ? 'bg-emerald-500/15 text-emerald-500'
              : 'text-(--color-text-muted) hover:bg-emerald-500/10 hover:text-emerald-500'
          }`}
          aria-label="Полезный план"
        >
          <ThumbsUp className="h-4 w-4" />
        </button>
        <button
          onClick={() => submit('down')}
          className={`p-2 rounded-lg transition-all ${
            rating === 'down'
              ? 'bg-red-500/15 text-red-500'
              : 'text-(--color-text-muted) hover:bg-red-500/10 hover:text-red-500'
          }`}
          aria-label="Бесполезный план"
        >
          <ThumbsDown className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
