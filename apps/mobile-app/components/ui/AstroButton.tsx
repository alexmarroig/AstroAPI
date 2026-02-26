import React from 'react';
import { TouchableOpacity, Text, TouchableOpacityProps } from 'react-native';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface AstroButtonProps extends TouchableOpacityProps {
  title: string;
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  textClassName?: string;
}

export function AstroButton({
  title,
  variant = 'primary',
  size = 'md',
  className,
  textClassName,
  ...props
}: AstroButtonProps) {
  const variants = {
    primary: 'bg-primary',
    secondary: 'bg-accent',
    outline: 'border border-primary bg-transparent',
    ghost: 'bg-transparent',
  };

  const sizes = {
    sm: 'px-4 py-2',
    md: 'px-6 py-3',
    lg: 'px-8 py-4',
  };

  const textVariants = {
    primary: 'text-white font-semibold',
    secondary: 'text-primary font-semibold',
    outline: 'text-primary font-semibold',
    ghost: 'text-primary font-semibold',
  };

  return (
    <TouchableOpacity
      className={cn(
        "rounded-full items-center justify-center transition-all active:opacity-80",
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    >
      <Text className={cn("text-base", textVariants[variant], textClassName)}>
        {title}
      </Text>
    </TouchableOpacity>
  );
}
