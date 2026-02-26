import React from 'react';
import { ScrollView, View, TouchableOpacity, Switch } from 'react-native';
import { Typography } from '@/components/ui/Typography';
import { Card } from '@/components/ui/Card';
import {
  User,
  Bell,
  Palette,
  CreditCard,
  MapPin,
  Settings,
  ChevronRight,
  LogOut,
  Info
} from 'lucide-react-native';

export default function MaisScreen() {
  const menuItems = [
    { label: 'Conta e Perfil', icon: User, color: '#3B82F6' },
    { label: 'Notificações', icon: Bell, color: '#F59E0B' },
    { label: 'Aparência', icon: Palette, color: '#8D5EE6' },
    { label: 'Planos e Assinatura', icon: CreditCard, color: '#10B981' },
    { label: 'Local e Fuso Horário', icon: MapPin, color: '#EF4444' },
    { label: 'Preferências de Leitura', icon: Settings, color: '#64748B' },
  ];

  return (
    <ScrollView className="flex-1 bg-background" showsVerticalScrollIndicator={false}>
      <View className="p-4">
        {/* Profile Summary */}
        <Card className="flex-row items-center p-6 mb-8">
          <View className="w-16 h-16 bg-accent rounded-full items-center justify-center mr-4">
            <Typography variant="h2" className="text-primary">C</Typography>
          </View>
          <View className="flex-1">
            <Typography variant="h3">Camila Bianco</Typography>
            <Typography variant="small" className="text-muted">Escorpião • ASC Touro</Typography>
          </View>
          <TouchableOpacity className="bg-background p-2 rounded-full">
            <Settings size={20} color="#94A3B8" />
          </TouchableOpacity>
        </Card>

        {/* Premium Banner */}
        <Card className="bg-primary/10 border border-primary/20 flex-row items-center p-4 mb-8">
          <View className="w-10 h-10 bg-primary rounded-xl items-center justify-center mr-4">
            <CreditCard size={20} color="#FFFFFF" />
          </View>
          <View className="flex-1">
            <Typography className="font-bold text-gray-900">Seja Premium</Typography>
            <Typography variant="small" className="text-gray-600">Libere trânsitos personalizados e muito mais.</Typography>
          </View>
          <Typography className="text-primary font-bold">Ver planos</Typography>
        </Card>

        {/* Menu List */}
        <Typography variant="h3" className="mb-4">Configurações</Typography>
        <Card className="p-0 overflow-hidden mb-8">
          {menuItems.map((item, i) => (
            <TouchableOpacity
              key={i}
              className={`flex-row items-center justify-between p-4 ${i !== menuItems.length - 1 ? 'border-b border-background' : ''}`}
            >
              <View className="flex-row items-center">
                <View className="w-8 h-8 rounded-lg items-center justify-center mr-3" style={{ backgroundColor: `${item.color}20` }}>
                  <item.icon size={18} color={item.color} />
                </View>
                <Typography className="font-medium text-gray-800">{item.label}</Typography>
              </View>
              <ChevronRight size={18} color="#94A3B8" />
            </TouchableOpacity>
          ))}
        </Card>

        {/* Other Actions */}
        <Typography variant="h3" className="mb-4">Outros</Typography>
        <Card className="p-0 overflow-hidden mb-8">
          <TouchableOpacity className="flex-row items-center justify-between p-4 border-b border-background">
            <View className="flex-row items-center">
              <Info size={18} color="#64748B" className="mr-3" />
              <Typography className="font-medium text-gray-800">Sobre o AstroAPI</Typography>
            </View>
            <ChevronRight size={18} color="#94A3B8" />
          </TouchableOpacity>
          <TouchableOpacity className="flex-row items-center justify-between p-4">
            <View className="flex-row items-center">
              <LogOut size={18} color="#EF4444" className="mr-3" />
              <Typography className="font-medium text-red-500">Sair da conta</Typography>
            </View>
          </TouchableOpacity>
        </Card>

        <Typography className="text-center text-muted text-xs mb-8">
          Versão 1.0.0 (Beta) • Feito com ❤️
        </Typography>
      </View>
    </ScrollView>
  );
}
