import React from 'react';
import Sidebar from './Sidebar';
import Header from './Header';

const Layout = ({ children, title, subtitle }) => {
  return (
    <div className="atlas-layout">
      <Sidebar />
      <div className="atlas-main">
        <Header title={title} subtitle={subtitle} />
        <div className="atlas-content">
          {children}
        </div>
      </div>
    </div>
  );
};

export default Layout;