import React from 'react';
import { ScrollView, View, TouchableOpacity } from 'react-native';
import { Typography } from '@/components/ui/Typography';
import { Card } from '@/components/ui/Card';
import {
  Moon,
  ChevronRight,
  Filter
} from 'lucide-react-native';

export default function ClimaScreen() {
  const eventos = [
    { data: '26 Jan', dia: 'Hoje', evento: 'Lua Crescente', signo: 'Touro', desc: 'Ideal para estabilizar projetos.', iconColor: '#3B82F6' },
    { data: '28 Jan', dia: 'Ter', evento: 'Vênus em Peixes', signo: 'Peixes', desc: 'Aumento da sensibilidade e empatia.', iconColor: '#EC4899' },
    { data: '30 Jan', dia: 'Qui', evento: 'Marte em Leão', signo: 'Leão', desc: 'Ação criativa e autoconfiança.', iconColor: '#EF4444' },
    { data: '02 Fev', dia: 'Dom', evento: 'Lua Cheia', signo: 'Leão', desc: 'Clímax emocional e visibilidade.', iconColor: '#F59E0B' },
  ];

  return (
    <ScrollView className="flex-1 bg-background" showsVerticalScrollIndicator={false}>
      <View className="p-4">
        <View className="flex-row justify-between items-center mb-6">
          <Typography variant="h1">Clima Cósmico</Typography>
          <TouchableOpacity className="bg-card p-2 rounded-full shadow-sm">
            <Filter size={20} color="#8D5EE6" />
          </TouchableOpacity>
        </View>

        {/* Phase Summary */}
        <Card className="items-center py-6 mb-6">
          <View className="w-20 h-20 bg-blue-50 rounded-full items-center justify-center mb-4">
            <Moon size={40} color="#3B82F6" fill="#3B82F6" opacity={0.2} />
          </View>
          <Typography variant="h3">Lua Crescente</Typography>
          <Typography variant="small" className="text-muted mt-1">Em Touro • 65% iluminada</Typography>
          <Typography className="text-center text-gray-600 mt-4 px-4">
            Um momento de crescimento constante. Foque em nutrir o que você começou na Lua Nova.
          </Typography>
        </Card>

        <View className="flex-row justify-between items-center mb-4">
          <Typography variant="h3">Próximos Eventos</Typography>
          <Typography variant="small" className="text-primary font-bold">Ver 30 dias</Typography>
        </View>

        {eventos.map((ev, i) => (
          <TouchableOpacity key={i} className="mb-4">
            <Card className="flex-row items-center p-4">
              <View className="items-center mr-4 w-12">
                <Typography className="font-bold text-gray-900">{ev.data.split(' ')[0]}</Typography>
                <Typography variant="small" className="text-muted uppercase text-[10px]">{ev.data.split(' ')[1]}</Typography>
              </View>
              <View className="w-1 h-10 bg-background rounded-full mr-4" />
              <View className="flex-1">
                <View className="flex-row items-center">
                  <View className="w-2 h-2 rounded-full mr-2" style={{ backgroundColor: ev.iconColor }} />
                  <Typography className="font-bold text-gray-900">{ev.evento}</Typography>
                </View>
                <Typography variant="small" className="text-gray-600 mt-0.5">{ev.signo} • {ev.desc}</Typography>
              </View>
              <ChevronRight size={18} color="#94A3B8" />
            </Card>
          </TouchableOpacity>
        ))}
      </View>
    </ScrollView>
  );
}
