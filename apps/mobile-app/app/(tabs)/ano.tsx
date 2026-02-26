import React from 'react';
import { ScrollView, View, TouchableOpacity } from 'react-native';
import { Typography } from '@/components/ui/Typography';
import { Card } from '@/components/ui/Card';
import {
  Calendar,
  Moon,
  Sun,
  ArrowUpRight,
  ChevronRight
} from 'lucide-react-native';

export default function AnoScreen() {
  const ciclos = [
    { title: 'Lunação Atual', subtitle: 'Lua Crescente em Aquário', date: 'Hoje', icon: Moon, color: 'bg-blue-100', iconColor: '#3B82F6' },
    { title: 'Revolução Solar', subtitle: 'Próximo aniversário', date: '15 Out 2025', icon: Sun, color: 'bg-orange-100', iconColor: '#F97316' },
    { title: 'Progressão Lunar', subtitle: 'Lua em Touro na Casa 2', date: 'Ativo', icon: ArrowUpRight, color: 'bg-purple-100', iconColor: '#8D5EE6' },
  ];

  return (
    <ScrollView className="flex-1 bg-background" showsVerticalScrollIndicator={false}>
      <View className="p-4">
        {/* Header Summary */}
        <Card className="bg-primary p-6 mb-6">
          <Typography className="text-white/80 font-medium">Seu Ciclo 2025</Typography>
          <Typography className="text-white text-2xl font-bold mt-1">Ano de Expansão e Novas Conexões</Typography>
          <View className="flex-row items-center mt-4">
            <View className="bg-white/20 px-3 py-1 rounded-full mr-2">
              <Typography className="text-white text-xs font-bold">FASE 2/4</Typography>
            </View>
            <Typography className="text-white/70 text-xs">Próximo grande evento em 12 dias</Typography>
          </View>
        </Card>

        <Typography variant="h3" className="mb-4">Ciclos Ativos</Typography>
        {ciclos.map((ciclo, i) => (
          <TouchableOpacity key={i} className="mb-4">
            <Card className="flex-row items-center p-4">
              <View className={`w-12 h-12 ${ciclo.color} rounded-2xl items-center justify-center mr-4`}>
                <ciclo.icon size={24} color={ciclo.iconColor} />
              </View>
              <View className="flex-1">
                <View className="flex-row justify-between items-center">
                  <Typography className="font-bold text-gray-900">{ciclo.title}</Typography>
                  <Typography variant="small" className="text-muted">{ciclo.date}</Typography>
                </View>
                <Typography variant="small" className="text-gray-600 mt-0.5">{ciclo.subtitle}</Typography>
              </View>
              <ChevronRight size={18} color="#94A3B8" className="ml-2" />
            </Card>
          </TouchableOpacity>
        ))}

        <Typography variant="h3" className="mb-4 mt-2">Linha do Tempo</Typography>
        <Card>
          {[1, 2, 3].map((_, i) => (
            <View key={i} className={`flex-row mb-6 ${i === 2 ? 'mb-0' : ''}`}>
              <View className="items-center mr-4">
                <View className="w-3 h-3 rounded-full bg-primary mt-1.5" />
                {i !== 2 && <View className="w-0.5 flex-1 bg-accent my-1" />}
              </View>
              <View className="flex-1 pb-4">
                <Typography className="font-bold text-gray-900">Mercúrio em Sagitário</Typography>
                <Typography variant="small" className="text-muted mb-2">04 Jan - 22 Jan</Typography>
                <Typography variant="small" className="text-gray-600">
                  Foco em estudos superiores e viagens longas. Comunicação expansiva.
                </Typography>
              </View>
            </View>
          ))}
        </Card>
      </View>
    </ScrollView>
  );
}
