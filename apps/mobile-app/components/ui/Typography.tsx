import React from 'react';
import { Text, TextProps } from 'react-native';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface TypographyProps extends TextProps {
  variant?: 'h1' | 'h2' | 'h3' | 'body' | 'small' | 'muted';
  className?: string;
}

export function Typography({
  variant = 'body',
  className,
  ...props
}: TypographyProps) {
  const variants = {
    h1: 'text-3xl font-bold text-gray-900',
    h2: 'text-2xl font-semibold text-gray-900',
    h3: 'text-xl font-medium text-gray-800',
    body: 'text-base text-gray-700',
    small: 'text-sm text-gray-600',
    muted: 'text-sm text-muted font-medium',
  };

  return <Text className={cn(variants[variant], className)} {...props} />;
}
