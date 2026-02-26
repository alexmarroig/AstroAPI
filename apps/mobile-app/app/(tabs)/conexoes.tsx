import React from 'react';
import { ScrollView, View, TouchableOpacity, TextInput } from 'react-native';
import { Typography } from '@/components/ui/Typography';
import { Card } from '@/components/ui/Card';
import { AstroButton } from '@/components/ui/AstroButton';
import {
  Plus,
  Search,
  Heart,
  Briefcase,
  Users,
  ChevronRight
} from 'lucide-react-native';

export default function ConexoesScreen() {
  const conexoes = [
    { name: 'João Silva', type: 'Amigo', match: 85, color: 'text-blue-500' },
    { name: 'Maria Souza', type: 'Amor', match: 92, color: 'text-pink-500' },
    { name: 'Pedro Alves', type: 'Trabalho', match: 74, color: 'text-orange-500' },
  ];

  return (
    <ScrollView className="flex-1 bg-background" showsVerticalScrollIndicator={false}>
      <View className="p-4">
        {/* Search & Add */}
        <View className="flex-row items-center mb-6 space-x-3">
          <View className="flex-1 flex-row items-center bg-card rounded-2xl px-4 py-3 shadow-sm">
            <Search size={20} color="#94A3B8" className="mr-2" />
            <TextInput
              placeholder="Buscar conexões..."
              className="flex-1 text-gray-900 text-base"
              placeholderTextColor="#94A3B8"
            />
          </View>
          <TouchableOpacity className="bg-primary p-4 rounded-2xl shadow-md">
            <Plus size={24} color="#FFFFFF" />
          </TouchableOpacity>
        </View>

        <Card className="bg-accent/30 border border-accent mb-8">
          <Typography className="font-bold text-lg mb-1">Nova Sinastria</Typography>
          <Typography variant="small" className="text-gray-600 mb-4">
            Adicione alguém para descobrir sua compatibilidade astral.
          </Typography>
          <AstroButton title="Começar Agora" size="sm" />
        </Card>

        <View className="flex-row justify-between items-center mb-4">
          <Typography variant="h3">Suas Conexões</Typography>
          <Typography variant="small" className="text-muted">{conexoes.length} perfis</Typography>
        </View>

        {conexoes.map((con, i) => (
          <TouchableOpacity key={i} className="mb-4">
            <Card className="flex-row items-center p-4">
              <View className="w-12 h-12 bg-background rounded-full items-center justify-center mr-4">
                {con.type === 'Amor' ? <Heart size={24} color="#EC4899" /> :
                 con.type === 'Trabalho' ? <Briefcase size={24} color="#F59E0B" /> :
                 <Users size={24} color="#3B82F6" />}
              </View>
              <View className="flex-1">
                <Typography className="font-bold text-gray-900">{con.name}</Typography>
                <Typography variant="small" className="text-muted">{con.type}</Typography>
              </View>
              <View className="items-end mr-2">
                <Typography className={`font-bold ${con.color}`}>{con.match}%</Typography>
                <Typography variant="small" className="text-[10px] text-muted uppercase">Match</Typography>
              </View>
              <ChevronRight size={18} color="#94A3B8" />
            </Card>
          </TouchableOpacity>
        ))}

        {/* Categories */}
        <Typography variant="h3" className="mb-4 mt-4">Categorias</Typography>
        <View className="flex-row justify-between">
          {[
            { label: 'Amor', icon: Heart, color: '#EC4899' },
            { label: 'Trabalho', icon: Briefcase, color: '#F59E0B' },
            { label: 'Família', icon: Users, color: '#3B82F6' },
          ].map((cat, i) => (
            <TouchableOpacity key={i} style={{ width: '31%' }}>
              <Card className="items-center p-4">
                <cat.icon size={24} color={cat.color} className="mb-2" />
                <Typography variant="small" className="font-bold">{cat.label}</Typography>
              </Card>
            </TouchableOpacity>
          ))}
        </View>
      </View>
    </ScrollView>
  );
}
