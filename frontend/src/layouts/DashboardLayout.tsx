import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopNavbar } from './TopNavbar';

export const DashboardLayout: React.FC = () => {
  return (
    <div className="min-h-screen bg-[#101216] text-[#ECEFF4] flex">
      {/* Sidebar Navigation */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <TopNavbar />
        <main className="flex-1 ml-64 p-6 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
