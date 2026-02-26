import React, { useState } from 'react';
import { ScrollView, View, TouchableOpacity, Dimensions } from 'react-native';
import { Typography } from '@/components/ui/Typography';
import { Card } from '@/components/ui/Card';
import Svg, { Circle, Line, Text as SvgText, G } from 'react-native-svg';
import {
  Sun,
  Moon,
  ChevronRight,
  Info
} from 'lucide-react-native';

const { width } = Dimensions.get('window');
const CHART_SIZE = width - 40;

export default function MapaScreen() {
  const [activeTab, setActiveTab] = useState('Planetas');

  const planetas = [
    { name: 'Sol', sign: 'Escorpião', degree: '24°', icon: Sun, color: 'text-orange-500' },
    { name: 'Lua', sign: 'Touro', degree: '12°', icon: Moon, color: 'text-blue-400' },
    { name: 'Mercúrio', sign: 'Escorpião', degree: '15°', color: 'text-purple-500' },
    { name: 'Vênus', sign: 'Sagitário', degree: '05°', color: 'text-pink-500' },
    { name: 'Marte', sign: 'Câncer', degree: '28°', color: 'text-red-500' },
  ];

  const distribution = [
    { label: 'Fogo', value: 25, color: 'bg-red-400' },
    { label: 'Terra', value: 15, color: 'bg-green-400' },
    { label: 'Ar', value: 30, color: 'bg-yellow-400' },
    { label: 'Água', value: 30, color: 'bg-blue-400' },
  ];

  return (
    <ScrollView className="flex-1 bg-background" showsVerticalScrollIndicator={false}>
      <View className="p-4">
        {/* Gráfico Natal (Placeholder SVG) */}
        <View className="items-center justify-center my-6">
          <Svg width={CHART_SIZE} height={CHART_SIZE} viewBox="0 0 200 200">
            {/* Outer circles */}
            <Circle cx="100" cy="100" r="95" stroke="#E5DEFF" strokeWidth="1" fill="#FFFFFF" />
            <Circle cx="100" cy="100" r="75" stroke="#E5DEFF" strokeWidth="1" fill="none" />
            <Circle cx="100" cy="100" r="45" stroke="#E5DEFF" strokeWidth="1" fill="none" />

            {/* 12 House lines */}
            {[...Array(12)].map((_, i) => (
              <Line
                key={i}
                x1="100"
                y1="100"
                x2={100 + 95 * Math.cos((i * 30 * Math.PI) / 180)}
                y2={100 + 95 * Math.sin((i * 30 * Math.PI) / 180)}
                stroke="#E5DEFF"
                strokeWidth="1"
              />
            ))}

            {/* Aspect lines (random examples) */}
            <Line x1="100 + 40 * Math.cos(45 * Math.PI / 180)" y1="100 + 40 * Math.sin(45 * Math.PI / 180)" x2="100 + 40 * Math.cos(180 * Math.PI / 180)" y2="100 + 40 * Math.sin(180 * Math.PI / 180)" stroke="#8D5EE6" strokeWidth="0.5" opacity="0.5" />

            <Circle cx="100" cy="100" r="15" fill="#F5F3FA" />
            <SvgText x="100" y="105" textAnchor="middle" fontSize="10" fill="#8D5EE6" fontWeight="bold">EU</SvgText>
          </Svg>
        </View>

        {/* Sub-tabs */}
        <View className="flex-row bg-card rounded-2xl p-1 mb-6">
          {['Planetas', 'Aspectos', 'Distribuição'].map((tab) => (
            <TouchableOpacity
              key={tab}
              onPress={() => setActiveTab(tab)}
              className={`flex-1 py-3 rounded-xl items-center ${activeTab === tab ? 'bg-primary' : ''}`}
            >
              <Typography className={`font-semibold ${activeTab === tab ? 'text-white' : 'text-muted'}`}>
                {tab}
              </Typography>
            </TouchableOpacity>
          ))}
        </View>

        {/* Tab Content */}
        {activeTab === 'Planetas' && (
          <View className="flex-row flex-wrap justify-between">
            {planetas.map((p, i) => (
              <TouchableOpacity key={i} style={{ width: '48%' }} className="mb-4">
                <Card className="p-4 items-center">
                  <View className="w-10 h-10 bg-background rounded-full items-center justify-center mb-2">
                    {p.icon ? <p.icon size={20} color="#8D5EE6" /> : <Typography className="text-primary font-bold">{p.name[0]}</Typography>}
                  </View>
                  <Typography className="font-bold text-gray-900">{p.name}</Typography>
                  <Typography variant="small" className="text-muted">{p.sign}</Typography>
                  <Typography variant="small" className="text-primary mt-1 font-semibold">{p.degree}</Typography>
                </Card>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {activeTab === 'Distribuição' && (
          <Card>
            <Typography className="font-bold mb-4">Elementos</Typography>
            {distribution.map((item, i) => (
              <View key={i} className="mb-4">
                <View className="flex-row justify-between mb-1">
                  <Typography variant="small" className="font-medium">{item.label}</Typography>
                  <Typography variant="small" className="text-muted">{item.value}%</Typography>
                </View>
                <View className="h-2 w-full bg-background rounded-full overflow-hidden">
                  <View
                    className={`h-full ${item.color}`}
                    style={{ width: `${item.value}%` }}
                  />
                </View>
              </View>
            ))}
          </Card>
        )}

        {activeTab === 'Aspectos' && (
          <Card className="p-0 overflow-hidden">
            {[1, 2, 3].map((_, i) => (
              <View key={i} className={`p-4 flex-row items-center justify-between ${i !== 2 ? 'border-b border-background' : ''}`}>
                <View className="flex-row items-center">
                  <View className="w-8 h-8 bg-blue-100 rounded-full items-center justify-center mr-3">
                    <Typography className="text-blue-600 text-xs">△</Typography>
                  </View>
                  <View>
                    <Typography className="font-bold text-sm">Sol Trígono Lua</Typography>
                    <Typography variant="small" className="text-muted">Harmonia interior</Typography>
                  </View>
                </View>
                <ChevronRight size={18} color="#94A3B8" />
              </View>
            ))}
          </Card>
        )}
      </View>
    </ScrollView>
  );
}
