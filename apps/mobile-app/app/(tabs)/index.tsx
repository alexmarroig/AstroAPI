import React from 'react';
import { ScrollView, View, Text, TouchableOpacity } from 'react-native';
import { Typography } from '@/components/ui/Typography';
import { Card } from '@/components/ui/Card';
import { ProgressCircle } from '@/components/ui/ProgressCircle';
import { AstroButton } from '@/components/ui/AstroButton';
import {
  Sparkles,
  MessageCircle,
  CheckCircle2,
  ChevronRight,
  AlertCircle
} from 'lucide-react-native';

export default function HojeScreen() {
  const energyItems = [
    { label: 'Emoções', value: 'Estável', color: 'text-blue-500' },
    { label: 'Relações', value: 'Harmonia', color: 'text-pink-500' },
    { label: 'Trabalho', value: 'Foco', color: 'text-orange-500' },
    { label: 'Corpo', value: 'Vitalidade', color: 'text-green-500' },
  ];

  const days = [
    { day: 'Dom', date: '25', active: false },
    { day: 'Seg', date: '26', active: true },
    { day: 'Ter', date: '27', active: false },
    { day: 'Qua', date: '28', active: false },
    { day: 'Qui', date: '29', active: false },
  ];

  return (
    <ScrollView className="flex-1 bg-background" showsVerticalScrollIndicator={false}>
      <View className="p-4 pt-2">
        {/* Próximos Dias Carousel */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} className="mb-6 -mx-4 px-4">
          {days.map((item, index) => (
            <TouchableOpacity
              key={index}
              className={`items-center justify-center w-16 h-20 rounded-2xl mr-3 ${item.active ? 'bg-primary' : 'bg-card'}`}
            >
              <Typography className={`text-xs ${item.active ? 'text-white' : 'text-muted'}`}>{item.day}</Typography>
              <Typography className={`text-lg font-bold ${item.active ? 'text-white' : 'text-gray-900'}`}>{item.date}</Typography>
              {item.active && <View className="w-1 h-1 bg-white rounded-full mt-1" />}
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Card de Energia */}
        <Card className="flex-row items-center justify-between py-6">
          <View className="flex-1">
            <Typography variant="h3" className="mb-1">Energia do dia</Typography>
            <Typography variant="small" className="mb-4">Sua vibração está em alta hoje</Typography>

            <View className="space-y-2">
              {energyItems.map((item, index) => (
                <View key={index} className="flex-row items-center">
                  <View className="w-1.5 h-1.5 rounded-full bg-primary mr-2" />
                  <Typography variant="small" className="text-gray-600 mr-2">{item.label}:</Typography>
                  <Typography variant="small" className={`font-semibold ${item.color}`}>{item.value}</Typography>
                </View>
              ))}
            </View>
          </View>
          <ProgressCircle progress={65} size={110} label="Favorável" />
        </Card>

        {/* Alertas do Céu */}
        <Typography variant="h3" className="mb-3 mt-2">Alertas do céu</Typography>
        <Card className="p-4 border-l-4 border-yellow-400">
          <View className="flex-row items-start">
            <AlertCircle size={20} color="#F59E0B" className="mr-3 mt-1" />
            <View className="flex-1">
              <Typography className="font-bold text-gray-900">Júpiter Retrógrado</Typography>
              <Typography variant="small" className="text-gray-600 mt-1">
                Um período para revisitar seus objetivos de longo prazo e crescimento interior.
              </Typography>
            </View>
            <ChevronRight size={20} color="#94A3B8" />
          </View>
        </Card>

        {/* Ação do Dia */}
        <Card className="bg-primary/5 border border-primary/10">
          <View className="flex-row items-center mb-3">
            <Sparkles size={20} color="#8D5EE6" className="mr-2" />
            <Typography className="font-bold text-primary">Ação do dia</Typography>
          </View>
          <Typography className="text-gray-800 mb-4">
            Dedique 10 minutos hoje para escrever suas intenções para a próxima fase lunar.
          </Typography>
          <AstroButton
            title="Marcar como feito"
            variant="outline"
            size="sm"
            className="self-start px-4 py-2 border-primary/30"
          />
        </Card>

        {/* Oráculo Astral (Chat) */}
        <TouchableOpacity className="mt-2 mb-8">
          <Card className="bg-accent/30 flex-row items-center justify-between border border-accent">
            <View className="flex-row items-center flex-1">
              <View className="w-12 h-12 bg-white rounded-2xl items-center justify-center mr-4 shadow-sm">
                <MessageCircle size={24} color="#8D5EE6" />
              </View>
              <View>
                <Typography className="font-bold text-gray-900">Oráculo Astral</Typography>
                <Typography variant="small" className="text-gray-600">Pergunte qualquer coisa ao céu...</Typography>
              </View>
            </View>
            <View className="bg-primary rounded-full px-3 py-1">
              <Typography className="text-[10px] text-white font-bold">IA</Typography>
            </View>
          </Card>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}
