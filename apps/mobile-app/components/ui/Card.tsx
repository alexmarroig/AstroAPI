import React from 'react';
import { View, ViewProps } from 'react-native';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface CardProps extends ViewProps {
  children: React.ReactNode;
  className?: string;
}

export function Card({ children, className, ...props }: CardProps) {
  return (
    <View
      className={cn("bg-card rounded-3xl p-5 shadow-sm mb-4", className)}
      {...props}
    >
      {children}
    </View>
  );
}
